console.log('Server script started.');  // This logs immediately to confirm the script runs

require('dotenv').config();
const express = require('express');
const nodemailer = require('nodemailer');
const { GoogleGenerativeAI } = require('@google/generative-ai');
const bodyParser = require('body-parser');
const mysql = require('mysql2');
const bcrypt = require('bcrypt');
const cors = require('cors');

console.log('Dependencies loaded.');  // Logs after all requires succeed

const app = express();
app.use(cors());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));
app.use(express.static('.'));

// ✅ Nodemailer
let transporter;
try {
  const allowSelfSignedCerts = process.env.ALLOW_SELF_SIGNED_CERTS === 'true';
  const emailDisabled = process.env.DISABLE_EMAIL === 'true';
  if (emailDisabled) {
    console.log('Email sending disabled by DISABLE_EMAIL=true');
    throw new Error('Email disabled');
  }
  transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
      user: process.env.EMAIL_USER,
      pass: process.env.EMAIL_PASS
    },
    // For environments with a proxy/self-signed MITM cert, allow opting in.
    ...(allowSelfSignedCerts ? { tls: { rejectUnauthorized: false } } : {})
  });
  console.log('Nodemailer configured.');
} catch (error) {
  console.error('Nodemailer setup error:', error);
}

async function sendMailSafe(options, label) {
  if (!transporter) return;
  try {
    await transporter.sendMail(options);
  } catch (err) {
    console.error(`${label} email error:`, err.message);
  }
}

// ✅ MySQL Pool
const db = mysql.createPool({
  host: 'localhost',
  user: 'root',
  password: process.env.DB_PASS || '',
  database: 'lifelinkdb'
});

// Test MySQL connection on startup
db.getConnection((err, conn) => {
  if (err) {
    console.error('MySQL connection error:', err.message);  // Logs the specific error
    console.log('Server will start without DB. Check credentials.');
    return;
  }
  console.log('Connected to MySQL');  // This logs on successful connection
  conn.release();

  // ✅ Create Tables (Run after connection is confirmed)
  const tables = [
    `CREATE TABLE IF NOT EXISTS users (
      id INT AUTO_INCREMENT PRIMARY KEY,
      fullname VARCHAR(255) NOT NULL,
      email VARCHAR(255) UNIQUE NOT NULL,
      phone VARCHAR(20),
      password VARCHAR(255) NOT NULL,
      role VARCHAR(50) DEFAULT 'user'
    );`,
    `CREATE TABLE IF NOT EXISTS login_logs (
      id INT AUTO_INCREMENT PRIMARY KEY,
      email VARCHAR(255) NOT NULL,
      login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,
    `CREATE TABLE IF NOT EXISTS predictions (
      id INT AUTO_INCREMENT PRIMARY KEY,
      userEmail VARCHAR(255),
      symptoms TEXT,
      aiResponse TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,
    `CREATE TABLE IF NOT EXISTS ambulance_bookings (
      id INT AUTO_INCREMENT PRIMARY KEY,
      name VARCHAR(255) NOT NULL,
      phone VARCHAR(20) NOT NULL,
      location TEXT NOT NULL,
      details TEXT,
      status VARCHAR(50) DEFAULT 'Pending',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`
  ];

  tables.forEach((query, index) => {
    db.query(query, (err) => {
      if (err) console.error(`Error creating table ${index + 1}:`, err);
      else console.log(`Table ${index + 1} created or exists.`);
    });
  });
});

// ✅ Register
app.post('/register', async (req, res) => {
  try {
    const { fullname, email, phone, password, role } = req.body;
    if (!fullname || !email || !password)
      return res.status(400).json({ error: 'Required fields missing' });

    const hashedPassword = await bcrypt.hash(password, 10);

    db.query(
      'INSERT INTO users (fullname, email, phone, password, role) VALUES (?, ?, ?, ?, ?)',
      [fullname, email, phone, hashedPassword, role],
      (err, result) => {
        if (err) {
          if (err.code === 'ER_DUP_ENTRY')
            return res.status(400).json({ error: 'Email already exists' });
          return res.status(500).json({ error: err.message });
        }

        // Send welcome email
        sendMailSafe({
          from: process.env.EMAIL_USER,
          to: email,
          subject: 'Welcome to LifeLink',
          text: `Hello ${fullname}, welcome to LifeLink!`
        }, 'Welcome');

        res.json({ message: 'User registered successfully' });
      }
    );
  } catch (error) {
    console.error('Register error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ✅ Login
app.post('/login', (req, res) => {
  try {
    const { email, password } = req.body;

    db.query(
      'SELECT * FROM users WHERE email = ?',
      [email],
      async (err, results) => {
        if (err) {
          return res.status(500).json({ message: 'DB error' });
        }

        if (results.length === 0) {
          return res.status(401).json({ message: 'User not found' });
        }

        const user = results[0];

        const isMatch = await bcrypt.compare(password, user.password);

        if (!isMatch) {
          return res.status(401).json({ message: 'Invalid password' });
        }

        db.query(
          'INSERT INTO login_logs (email) VALUES (?)',
          [email],
          (err2) => {
            if (err2) console.log('Login log error:', err2);
          }
        );

        res.json({ message: 'Login successful' });
      }
    );
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ✅ AI Prediction
app.post("/predict", async (req, res) => {
  try {
    const { userEmail, symptoms } = req.body;

    if (!symptoms) {
      return res.status(400).json({ error: "Symptoms required" });
    }

    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

    const model = genAI.getGenerativeModel({
      model: "gemini-3-flash-preview"
    });

    const prompt = `
Symptoms: ${symptoms}

Predict:
Disease:
Severity:
Precautions:
Ambulance required (yes/no):
`;

    const result = await model.generateContent(prompt);
    const aiText = result.response.text();

    db.query(
      "INSERT INTO predictions (userEmail, symptoms, aiResponse) VALUES (?, ?, ?)",
      [userEmail, symptoms, aiText]
    );

    res.json({ aiResponse: aiText });

  } catch (error) {
    console.error("Gemini Error:", error);
    res.status(500).json({ error: "AI prediction failed" });
  }
});

// ✅ Ambulance Booking API
app.post('/api/book-ambulance', (req, res) => {
  try {
    const { name, phone, location, details } = req.body;
    if (!name || !phone || !location) {
      return res.status(400).json({ error: 'Name, phone, and location are required' });
    }

    db.query(
  'INSERT INTO ambulance_bookings (name, phone, location, details, status) VALUES (?, ?, ?, ?, ?)',
  [name, phone, location, details || null, 'Pending'],

      (err, result) => {
        if (err) {
          return res.status(500).json({ error: 'Database error' });
        }

        // Notify admin via email
        sendMailSafe({
          from: process.env.EMAIL_USER,
          to: process.env.ADMIN_EMAIL || 'ksrashmi991@gmail.com',
          subject: 'New Ambulance Booking',
          text: `New booking from ${name} (${phone}) at ${location}. Details: ${details || 'None'}`
        }, 'Booking notify');

        res.json({ message: 'Booking submitted successfully', id: result.insertId });
      }
    );
  } catch (error) {
    console.error('Booking error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ✅ Get All Bookings
app.get('/api/bookings', (req, res) => {
  try {
    db.query('SELECT * FROM ambulance_bookings ORDER BY created_at DESC', (err, results) => {
      if (err) {
        return res.status(500).json({ error: 'Database error' });
      }
      res.json(results);
    });
  } catch (error) {
    console.error('Get bookings error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ✅ Update Booking Status
app.put('/api/bookings/:id', (req, res) => {
  try {
    const { status } = req.body;
    const id = req.params.id;

    db.query(
      'UPDATE ambulance_bookings SET status = ? WHERE id = ?',
      [status, id],
      (err) => {
        if (err) {
          return res.status(500).json({ error: 'Update failed' });
        }

        if (status === 'Dispatched') {
          db.query('SELECT * FROM ambulance_bookings WHERE id = ?', [id], (err, results) => {
            if (results.length > 0) {
              const booking = results[0];
              const userEmail = 'user@example.com';  // Placeholder
              if (transporter) {
                sendMailSafe({
                  from: process.env.EMAIL_USER,
                  to: userEmail,
                  subject: 'Ambulance Dispatched',
                  text: `Ambulance is on the way to ${booking.location}. Details: ${booking.details || 'None'}`
                }, 'Dispatched notify');
              }
            }
          });
        }

        res.json({ message: 'Status updated successfully' });
      }
    );
  } catch (error) {
    console.error('Update booking error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ✅ Start Server
const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);  // This logs when the server successfully starts
});
