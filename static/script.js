const summarizeButton = document.getElementById('summarizeButton');
const matchButton = document.getElementById('matchButton');
const loader = document.getElementById('loader');
const timeRemainingElement = document.getElementById('timeRemaining');
const resultsDiv = document.getElementById('results');
const downloadCsvButton = document.getElementById('downloadCsvButton');
const downloadFilteredCsvButton = document.getElementById('downloadFilteredCsvButton');
const shortlistButton = document.getElementById('shortlistButton');
const categoryFilters = document.getElementById('categoryFilters');
const percentageThresholdSelect = document.getElementById('percentageThreshold');
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('resumes');
const fileList = document.getElementById('file-list');
const dropzoneText = document.getElementById('dropzone-text');
const fileCount = document.getElementById('file-count');

let summarizedData = [];
let matchData = [];
let categorizedResults = {};
let currentAction = '';
let countdownInterval;
let currentCategory = ''; // Track the currently selected category



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
    currentAction = action;

    loader.style.display = 'block';
    downloadCsvButton.style.display = 'none';
    downloadFilteredCsvButton.style.display = 'none';
    shortlistButton.style.display = 'none';
    categoryFilters.style.display = 'none';
    resultsDiv.innerHTML = '';

    const numberOfResumes = formData.getAll('resumes').length;
    let estimatedTime = action === 'summarize' ? numberOfResumes * 5 : numberOfResumes * 4;

    startCountdown(estimatedTime);

    try {
        const response = await axios.post('/process_resumes', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });

        const data = response.data;
        const results = data.results || [];
        categorizedResults = data.categorized_results || {};

        if (action === 'summarize') {
            summarizedData = results;
        } else if (action === 'match') {
            matchData = results;
        }

        displayResults(results, action);
        categoryFilters.style.display = 'block';
        downloadCsvButton.style.display = 'inline-block';
        downloadFilteredCsvButton.style.display = 'inline-block';
        if (action === 'match') {
            shortlistButton.style.display = 'inline-block';
        }

        setupCategoryFilters();
        setupPercentageFilter();
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
        timeRemainingElement.innerHTML = `Estimated Time Remaining: ${minutes} minute${minutes !== 1 ? 's' : ''} ${seconds} second${seconds !== 1 ? 's' : ''}`;
        timeLeft--;
        if (timeLeft < 0) {
            clearInterval(countdownInterval);
            timeRemainingElement.innerHTML = 'Processing complete!';
        }
    }, 1000);
};

// Function to format experience text
const formatExperience = (experienceText) => {
    if (!experienceText || experienceText === "N/A") return "N/A";

    // Split on newlines (\n), "(n -", or " - " (for cases like the second candidate)
    let experiences = experienceText.includes("(n -")
        ? experienceText.split("(n -")
        : experienceText.includes(" - ")
            ? experienceText.split(" - ").filter(e => e.trim() !== "")
            : experienceText.split("\n").filter(e => e.trim() !== "");

    // Clean and format each experience
    const formattedExperiences = experiences.map(exp => {
        // Remove unwanted symbols
        let cleanExp = exp.replace(/[\*\[\]":]+/g, "").trim();

        // Split into components (assuming format: "Company, Role, Duration")
        const parts = cleanExp.split(", ").map(part => part.trim());
        if (parts.length >= 3) {
            const company = parts[0];
            const role = parts[1];
            const duration = parts.slice(2).join(", "); // Join remaining parts as duration
            return `${company} - ${role}, ${duration}`;
        }
        return cleanExp; // Fallback if parsing fails
    });

    // Join with <br> for new lines
    return formattedExperiences.join("<br>");
};

// Function to format lacking text
const formatLacking = (lackingText) => {
    if (!lackingText || lackingText === "N/A") return "N/A";

    // Split on newlines (\n) or use numbering pattern (e.g., "2.")
    let items = lackingText.includes("\n")
        ? lackingText.split("\n")
        : lackingText.split(/(?=\d+\.\s)/).filter(item => item.trim() !== "");

    // Clean and format each item
    const formattedItems = items.map(item => {
        // Remove unwanted symbols
        return item.replace(/[\*\[\]":]+/g, "").trim();
    });

    // Join with <br> for new lines
    return formattedItems.join("<br>");
};

const displayResults = (results, action) => {
    const percentageThreshold = parseFloat(percentageThresholdSelect.value) || 0;
    const selectedCategories = Array.from(document.querySelectorAll('.category-checkbox:checked'))
        .map(checkbox => checkbox.value);

    // Filter results by percentage match (only for match action)
    let filteredResults = results;
    if (action === 'match') {
        filteredResults = results.filter(result => {
            const percentage = parseFloat(result.percentage_match.replace('%', '')) || 0;
            return percentage >= percentageThreshold;
        });
    }

    // Sort by percentage match if action is 'match'
    if (action === 'match') {
        filteredResults.sort((a, b) => {
            let percentA = parseFloat(a.percentage_match.replace('%', '')) || 0;
            let percentB = parseFloat(b.percentage_match.replace('%', '')) || 0;
            return percentB - percentA;
        });
    }

    let output = '<h2>Results</h2>';

    // Display the applied filters
    output += '<p><strong>Applied Filters:</strong> ';
    if (percentageThreshold > 0 && selectedCategories.length > 0) {
        output += `Percentage Match >= ${percentageThreshold}%, Categories: ${selectedCategories.join(', ')}`;
    } else if (percentageThreshold > 0) {
        output += `Percentage Match >= ${percentageThreshold}%`;
    } else if (selectedCategories.length > 0) {
        output += `Categories: ${selectedCategories.join(', ')}`;
    } else {
        output += 'None';
    }
    output += '</p>';

    if (filteredResults.length === 0) {
        output += '<p>No results found for the selected filters.</p>';
    } else {
        output += '<ul class="list-group">';
        filteredResults.forEach((result) => {
            output += `<li class="list-group-item" style="margin-bottom: 15px; padding: 15px;">
                <div style="display: grid; grid-template-columns: 180px 1fr; gap: 10px;">
                    <strong>Filename:</strong> <span>${result.filename || "N/A"}</span>
                    <strong>Categories:</strong> <span>${result.categories?.join(', ') || "N/A"}</span>
                    <strong>Specific Role:</strong> <span>${result.specific_role || "N/A"}</span>`;

            if (action === 'summarize') {
                output += `
                    <strong>Name:</strong> <span>${result.name || "N/A"}</span>
                    <strong>Email:</strong> <span>${result.email || "N/A"}</span>
                    <strong>Phone:</strong> <span>${result.phone || "N/A"}</span>
                    <strong>Qualification:</strong> <span>${result.qualification || "N/A"}</span>
                    <strong>Experience:</strong> <div>${formatExperience(result.experience)}</div>
                    <strong>Skills:</strong> <span>${result.skills || "N/A"}</span>
                    <strong>Evaluation:</strong> <span>${result.evaluation || "N/A"}</span>
                    <strong>Personality:</strong> <span>${result.personal_evaluation || "N/A"}</span>`;
            } else if (action === 'match') {
                output += `
                    <strong>Percentage Match:</strong> <span>${result.percentage_match || "N/A"}</span>
                    <strong>Justification:</strong> <span>${result.justification || "N/A"}</span>
                    <strong>Lacking:</strong> <div>${formatLacking(result.lacking)}</div>`;
            }

            output += `</div></li>`;
        });
        output += '</ul>';
    }

    resultsDiv.innerHTML = output;
};

const setupCategoryFilters = () => {
    const buttons = document.querySelectorAll('.category-btn');
    buttons.forEach(button => {
        button.onclick = () => {
            currentCategory = button.getAttribute('data-category');
            buttons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            if (currentCategory) {
                const filteredResults = categorizedResults[currentCategory] || [];
                displayResults(filteredResults, currentAction);
            } else {
                displayResults(currentAction === 'summarize' ? summarizedData : matchData, currentAction);
            }
        };
    });
};

const setupPercentageFilter = () => {
    percentageThresholdSelect.onchange = () => {
        // Refresh the displayed results based on the current category and new percentage threshold
        if (currentCategory) {
            const filteredResults = categorizedResults[currentCategory] || [];
            displayResults(filteredResults, currentAction);
        } else {
            displayResults(currentAction === 'summarize' ? summarizedData : matchData, currentAction);
        }
    };
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
            { headers: { 'Content-Type': 'application/json' } }
        );

        if (response.data.job_description) {
            document.getElementById('jobDescription').value = response.data.job_description;
        } else {
            alert("Failed to generate JD. Try again.");
        }
    } catch (error) {
        alert("Error fetching JD: Check the console for details.");
    } finally {
        document.getElementById('jobDescription').placeholder = "Enter the job description here...";
    }
};

downloadCsvButton.onclick = async () => {
    const percentageThreshold = parseFloat(percentageThresholdSelect.value) || 0;

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
        const response = await axios.post('/download_csv', {
            summarized_data: dataToExport,
            percentage_threshold: percentageThreshold
        }, {
            headers: { 'Content-Type': 'application/json' },
            responseType: 'blob',
        });

        const blob = new Blob([response.data], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = 'summary_all.csv';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
    } catch (err) {
        alert('Error downloading CSV. Please try again.');
    }
};

downloadFilteredCsvButton.onclick = async () => {
    const percentageThreshold = parseFloat(percentageThresholdSelect.value) || 0;
    const selectedCategories = Array.from(document.querySelectorAll('.category-checkbox:checked'))
        .map(checkbox => checkbox.value);

    if (selectedCategories.length === 0) {
        alert('Please select at least one category to download.');
        return;
    }

    const filteredData = [];
    summarizedData.forEach((summarized) => {
        const match = matchData.find((m) => m.filename === summarized.filename) || {};
        const combined = {
            ...summarized,
            percentage_match: match.percentage_match || "N/A",
            justification: match.justification || "N/A",
            lacking: match.lacking || "N/A",
        };
        if (summarized.categories.some(category => selectedCategories.includes(category))) {
            filteredData.push(combined);
        }
    });

    const dataToExport = filteredData.length > 0 ? filteredData : matchData.filter(item =>
        item.categories.some(category => selectedCategories.includes(category))
    );

    try {
        const response = await axios.post('/download_filtered_csv', {
            summarized_data: dataToExport,
            categories: selectedCategories,
            percentage_threshold: percentageThreshold
        }, {
            headers: { 'Content-Type': 'application/json' },
            responseType: 'blob',
        });

        const blob = new Blob([response.data], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `summary_${selectedCategories.join('_')}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
    } catch (err) {
        alert('Error downloading filtered CSV. Please try again.');
    }
};

shortlistButton.onclick = async () => {
    const percentageThreshold = parseFloat(percentageThresholdSelect.value) || 0;
    const selectedCategories = Array.from(document.querySelectorAll('.category-checkbox:checked'))
        .map(checkbox => checkbox.value);

    // Optional: Warn the user if no filters are applied
    if (percentageThreshold === 0 && selectedCategories.length === 0) {
        const confirm = window.confirm('No percentage threshold or categories selected. All matched resumes will be shortlisted. Proceed?');
        if (!confirm) return;
    }

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
        const response = await axios.post('/shortlist_resumes', {
            summarized_data: dataToExport,
            percentage_threshold: percentageThreshold,
            categories: selectedCategories  // Pass selected categories to the backend
        }, {
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.data.message) {
            alert(response.data.message);
        } else {
            alert('Failed to shortlist resumes. Please try again.');
        }
    } catch (err) {
        alert('Error shortlisting resumes: ' + (err.response?.data?.error || 'Please try again.'));
    }
};
dropzone.addEventListener('click', () => fileInput.click());

// Handle file selection
fileInput.addEventListener('change', () => {
    updateFileDisplay();
});

// Drag and drop events
dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = '#0d6efd';
    dropzone.style.backgroundColor = '#f0f7ff';
});

dropzone.addEventListener('dragleave', () => {
    dropzone.style.borderColor = '#ccc';
    dropzone.style.backgroundColor = '';
});

dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = '#ccc';
    dropzone.style.backgroundColor = '';
    
    if (e.dataTransfer.files.length) {
        // Combine existing files with new ones
        const existingFiles = Array.from(fileInput.files);
        const newFiles = Array.from(e.dataTransfer.files);
        const combinedFiles = [...existingFiles, ...newFiles];
        
        // Create new DataTransfer and add all files
        const dt = new DataTransfer();
        combinedFiles.forEach(file => dt.items.add(file));
        
        fileInput.files = dt.files;
        updateFileDisplay();
    }
});

// Update the file display
function updateFileDisplay() {
    const files = fileInput.files;
    fileList.innerHTML = '';
    
    if (!files.length) {
        fileCount.textContent = 'No files selected';
        dropzoneText.textContent = 'Drag & drop PDF files here or click to browse';
        return;
    }
    
    // Update file count
    fileCount.textContent = `${files.length} file(s) selected`;
    
    // Create file list
    const list = document.createElement('ul');
    list.className = 'list-group';
    
    Array.from(files).forEach((file, index) => {
        const item = document.createElement('li');
        item.className = 'list-group-item d-flex justify-content-between align-items-center';
        item.innerHTML = `
            <span>${file.name}</span>
            <span class="badge bg-secondary rounded-pill">${(file.size/1024).toFixed(1)}KB</span>
            <button class="btn btn-sm btn-outline-danger" onclick="removeFile(${index})">
                <i class="fas fa-times"></i>
            </button>
        `;
        list.appendChild(item);
    });
    
    fileList.appendChild(list);
}

// Remove file function
window.removeFile = function(index) {
    const dt = new DataTransfer();
    const files = fileInput.files;
    
    for (let i = 0; i < files.length; i++) {
        if (i !== index) dt.items.add(files[i]);
    }
    
    fileInput.files = dt.files;
    updateFileDisplay();
};