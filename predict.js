// Function to add symptoms from icon clicks to the textarea
function addSymptom(symptom) {
  const textarea = document.getElementById('symptomText');
  const currentText = textarea.value.trim();
  if (currentText) {
    textarea.value = currentText + ', ' + symptom;
  } else {
    textarea.value = symptom;
  }
}

// Function to analyze symptoms and provide manual precautions or redirect
function analyzeSymptoms() {
  const symptomText = document.getElementById('symptomText').value.trim().toLowerCase();
  const resultDiv = document.getElementById('result');

  // Hide previous results
  resultDiv.style.display = 'none';
  resultDiv.innerHTML = '';

  // Check for empty input
  if (!symptomText) {
    alert('Please enter or select some symptoms.');
    return;
  }

  // Define serious symptoms (case-insensitive keywords)
  const seriousSymptoms = [
    'chest pain', 'breathing difficulty', 'high fever', 'loss of taste', 'loss of smell',
    'severe pain', 'unconscious', 'bleeding', 'fracture', 'stroke', 'heart attack'
  ];

  // Check if any serious symptom is present
  const isSerious = seriousSymptoms.some(symptom => symptomText.includes(symptom));

  if (isSerious) {
    // Serious symptoms detected: Redirect to ambulance booking
    alert('Serious symptoms detected. Redirecting to ambulance booking for immediate help.');
    window.location.href = 'ambulance-booking.html';  // Adjust path if needed
  } else {
    // Not serious: Display manual precaution measures
    const precautions = `
      <h4>Manual Precaution Measures</h4>
      <p>Based on your symptoms, here are some general steps to take until professional help arrives:</p>
      <ul>
        <li><strong>Rest and Monitor:</strong> Stay in a comfortable, quiet place and keep track of your symptoms (e.g., temperature, pain level).</li>
        <li><strong>Hydrate:</strong> Drink plenty of water or clear fluids to stay hydrated.</li>
        <li><strong>Over-the-Counter Relief:</strong> If appropriate, use pain relievers like acetaminophen (e.g., Tylenol) for fever or pain, but avoid aspirin if you suspect heart issues.</li>
        <li><strong>Avoid Triggers:</strong> Stay away from smoke, allergens, or strenuous activities that worsen symptoms.</li>
        <li><strong>Seek Help if Worsens:</strong> If symptoms intensify (e.g., difficulty breathing, severe pain), contact emergency services immediately.</li>
        <li><strong>Consult a Doctor:</strong> This is not medical advice. Schedule an appointment or visit a clinic soon.</li>
      </ul>
      <p><em>Remember: These are general suggestions. Always prioritize your health and consult a healthcare professional.</em></p>
    `;

    resultDiv.innerHTML = precautions;
    resultDiv.style.display = 'block';
  }
}