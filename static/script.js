const summarizeButton = document.getElementById('summarizeButton');
const matchButton = document.getElementById('matchButton');
const loader = document.getElementById('loader');
const timeRemainingElement = document.getElementById('timeRemaining');
const resultsDiv = document.getElementById('results');
const downloadCsvButton = document.getElementById('downloadCsvButton');

let summarizedData = [];
let matchData = [];

summarizeButton.onclick = () => submitForm('summarize');
matchButton.onclick = () => {
    const jobDescription = document.getElementById('jobDescription').value.trim();
    if (!jobDescription) {
        alert('Please provide a job description to perform percentage match.');
        return;
    }
    submitForm('match');
};

const submitForm = async (action) => {
    const formData = new FormData(document.getElementById('resumeForm'));
    formData.append('action', action);

    loader.style.display = 'block';
    downloadCsvButton.style.display = 'none';
    resultsDiv.innerHTML = '';

    const numberOfResumes = formData.getAll('resumes').length;
    let estimatedTime;
    if (action === 'summarize') {
        estimatedTime = numberOfResumes * 5;  // 5 seconds per resume for summarizing
    } else if (action === 'match') {
        estimatedTime = numberOfResumes * 4 ;  // 4 seconds per resume for percentage match
    }

    // Start the countdown
    startCountdown(estimatedTime);

    try {
        const response = await axios.post('/process_resumes', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });

        const results = response.data;

        if (action === 'summarize') {
            summarizedData = results;
        } else if (action === 'match') {
            matchData = results;
        }

        displayResults(results, action);
        downloadCsvButton.style.display = 'inline-block';
    } catch (err) {
        alert('Error processing resumes. Please try again.');
    } finally {
        loader.style.display = 'none';
        clearInterval(countdownInterval);
        timeRemainingElement.innerHTML = 'Processing complete!';
    }
};

const startCountdown = (timeInSeconds) => {
    let timeLeft = timeInSeconds;

    countdownInterval = setInterval(() => {
        let minutes = Math.floor(timeLeft / 60);  
        let seconds = timeLeft % 60;  

        // Update the time display in minutes and seconds format
        timeRemainingElement.innerHTML = `Estimated Time Remaining: ${minutes} minute${minutes !== 1 ? 's' : ''} ${seconds} second${seconds !== 1 ? 's' : ''}`;

        timeLeft--;

        if (timeLeft < 0) {
            clearInterval(countdownInterval);
            timeRemainingElement.innerHTML = 'Processing complete!';
        }
    }, 1000);
};


const displayResults = (results, action) => { 
    let output = '<h2>Results</h2><ul class="list-group">';

    if (action === 'match') {
        // Sort results by percentage_match in descending order
        results.sort((a, b) => {
            let percentA = parseFloat(a.percentage_match.replace('%', '')) || 0;
            let percentB = parseFloat(b.percentage_match.replace('%', '')) || 0;
            return percentB - percentA;  // Highest to lowest sorting
        });
    }

    results.forEach((result) => {
        output += `<li class="list-group-item">
            <strong>Filename:</strong> ${result.filename || "N/A"}<br>`;

        if (action === 'summarize') {
            output += `
                <strong>Name:</strong> ${result.name || "N/A"}<br>
                <strong>Email:</strong> ${result.email || "N/A"}<br>
                <strong>Phone:</strong> ${result.phone || "N/A"}<br>
                <strong>Qualification:</strong> ${result.qualification || "N/A"}<br>
                <strong>Experience:</strong> ${result.experience || "N/A"}<br>
                <strong>Skills:</strong> ${result.skills || "N/A"}<br>
                <strong>Evaluation:</strong> ${result.evaluation || "N/A"}<br>`;
        } else if (action === 'match') {
            output += `
                <strong>Percentage Match:</strong> ${result.percentage_match || "N/A"}<br>
                <strong>Justification:</strong> ${result.justification || "N/A"}<br>
                <strong>Lacking:</strong> ${result.lacking || "N/A"}<br>`;
        }

        output += `</li>`;
    });

    output += '</ul>';
    resultsDiv.innerHTML = output;
};

document.getElementById('generateJD').onclick = async () => {
    const jobRole = document.getElementById('jobRole').value.trim();
    if (!jobRole) {
        alert("Please enter a job role.");
        return;
    }

    try {
        document.getElementById('jobDescription').placeholder = "Generating JD...";
        
        const response = await axios.post('/generate_jd', 
            { job_role: jobRole }, 
            { headers: { 'Content-Type': 'application/json' } } // Ensure JSON format
        );

        if (response.data.job_description) {
            document.getElementById('jobDescription').value = response.data.job_description;
        } else {
            console.error("Response error:", response.data);
            alert("Failed to generate JD. Try again.");
        }
    } catch (error) {
        console.error("Error fetching JD:", error);
        alert("Error fetching JD: Check the console for details.");
    } finally {
        document.getElementById('jobDescription').placeholder = "Enter the job description here...";
    }
};


// Function to clean the JD text
const cleanText = (text) => {
    return text.replace(/[*_]/g, '').trim();  // Removes asterisks, underscores, and trims whitespace
};



downloadCsvButton.onclick = async () => {
    const combinedData = [];
    summarizedData.forEach((summarized) => {
        const match = matchData.find((m) => m.filename === summarized.filename) || {};
        combinedData.push({
            ...summarized,
            percentage_match: match.percentage_match || "N/A",
            justification: match.justification || "N/A",
            lacking: match.lacking || "N/A",
        });
    });

    const dataToExport = summarizedData.length > 0 ? combinedData : matchData;

    try {
        const response = await axios.post('/download_csv', { summarized_data: dataToExport }, {
            headers: { 'Content-Type': 'application/json' },
            responseType: 'blob',
        });

        const blob = new Blob([response.data], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = 'summary.csv';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
    } catch (err) {
        alert('Error downloading CSV. Please try again.');
    }
};
