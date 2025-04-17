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
const fileCount = document.getElementById('file-count');
const viewFilesButton = document.getElementById('viewFilesButton');
const modalFileList = document.getElementById('modalFileList');
const visualizationDiv = document.getElementById('visualization');

const SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.png', '.jpg', '.jpeg'];

let summarizedData = [];
let matchData = [];
let categorizedResults = {};
let currentAction = '';
let currentDisplayCategory = ''; // Tracks the category for results display
let countdownInterval;
let currentCategory = ''; // Tracks the category for download filters
let pieChart, barChart; // Chart instances

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
    visualizationDiv.style.display = 'none';
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

        displayResults(results, action, currentDisplayCategory); // Use currentDisplayCategory for results
        categoryFilters.style.display = 'block';
        downloadCsvButton.style.display = 'inline-block';
        downloadFilteredCsvButton.style.display = 'inline-block';
        if (action === 'match') {
            shortlistButton.style.display = 'inline-block';
        }

        setupCategoryFilters();
        setupPercentageFilter();
        displayCharts(); // Render charts after processing
    } catch (err) {
        const errorMessage = err.response?.data?.error || 'Error processing resumes. Please try again.';
        alert(errorMessage);
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

const formatExperience = (experienceText) => {
    if (!experienceText || experienceText === "N/A") return "N/A";

    let experiences = experienceText.includes("(n -")
        ? experienceText.split("(n -")
        : experienceText.includes(" - ")
            ? experienceText.split(" - ").filter(e => e.trim() !== "")
            : experienceText.split("\n").filter(e => e.trim() !== "");

    const formattedExperiences = experiences.map(exp => {
        let cleanExp = exp.replace(/[\*\[\]":]+/g, "").trim();
        const parts = cleanExp.split(", ").map(part => part.trim());
        if (parts.length >= 3) {
            const company = parts[0];
            const role = parts[1];
            const duration = parts.slice(2).join(", ");
            return `${company} - ${role}, ${duration}`;
        }
        return cleanExp;
    });

    return formattedExperiences.join("<br>");
};

const formatLacking = (lackingText) => {
    if (!lackingText || lackingText === "N/A") return "N/A";

    let items = lackingText.includes("\n")
        ? lackingText.split("\n")
        : lackingText.split(/(?=\d+\.\s)/).filter(item => item.trim() !== "");

    const formattedItems = items.map((item, index) => {
        return item.replace(/[\*\[\]":]+/g, "").trim() || `Item ${index + 1}`;
    }).filter(item => item !== "Item 0");

    return formattedItems.map((item, index) => `${index + 1}. ${item}`).join("<br>");
};

const displayResults = (results, action, displayCategory) => {
    const percentageThreshold = parseFloat(percentageThresholdSelect.value) || 0;
    let filteredResults = results;

    if (action === 'match') {
        filteredResults = results.filter(result => {
            const percentage = parseFloat(result.percentage_match.replace('%', '')) || 0;
            return percentage >= percentageThreshold;
        });
    }

    if (displayCategory && categorizedResults[displayCategory]) {
        filteredResults = categorizedResults[displayCategory];
    }

    if (action === 'match') {
        filteredResults.sort((a, b) => {
            let percentA = parseFloat(a.percentage_match.replace('%', '')) || 0;
            let percentB = parseFloat(b.percentage_match.replace('%', '')) || 0;
            return percentB - percentA;
        });
    }

    const selectedCategories = Array.from(document.querySelectorAll('.category-checkbox:checked'))
        .map(checkbox => checkbox.value); // This is for download filters, not results

    let output = '<h2>Results</h2>';
    output += '<p><strong>Applied Filters:</strong> ';
    if (percentageThreshold > 0) {
        output += `Percentage Match >= ${percentageThreshold}%`;
    }
    if (displayCategory) {
        output += `${percentageThreshold > 0 ? ', ' : ''}Category: ${displayCategory}`;
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
            currentDisplayCategory = button.getAttribute('data-category'); // Update for results display
            buttons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            if (currentDisplayCategory) {
                const filteredResults = categorizedResults[currentDisplayCategory] || [];
                displayResults(currentAction === 'summarize' ? summarizedData : matchData, currentAction, currentDisplayCategory);
            } else {
                displayResults(currentAction === 'summarize' ? summarizedData : matchData, currentAction, '');
            }
            displayCharts(); // Update charts when category changes
        };
    });
};

const setupPercentageFilter = () => {
    percentageThresholdSelect.onchange = () => {
        displayResults(currentAction === 'summarize' ? summarizedData : matchData, currentAction, currentDisplayCategory);
        displayCharts(); // Update charts when percentage filter changes
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
            summarized_data: dataToExport
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
        alert(`Error downloading CSV: ${err.response?.data?.error || 'Please try again.'}`);
        console.error('CSV Download Error:', err);
    }
};

downloadFilteredCsvButton.onclick = async () => {
    const percentageThreshold = parseFloat(document.getElementById('downloadPercentageThreshold').value) || 0;
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
        if (summarized.categories?.some(category => selectedCategories.includes(category))) {
            filteredData.push(combined);
        }
    });

    const dataToExport = filteredData.length > 0 ? filteredData : matchData.filter(item =>
        item.categories?.some(category => selectedCategories.includes(category))
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
        alert(`Error downloading filtered CSV: ${err.response?.data?.error || 'Please try again.'}`);
        console.error('Filtered CSV Download Error:', err);
    }
};

shortlistButton.onclick = async () => {
    const percentageThreshold = parseFloat(document.getElementById('downloadPercentageThreshold').value) || 0;
    const selectedCategories = Array.from(document.querySelectorAll('.category-checkbox:checked'))
        .map(checkbox => checkbox.value);

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
    const filteredResumes = dataToExport.filter(result => {
        const percentage = parseFloat(result.percentage_match.replace('%', '')) || 0;
        const categoryMatch = selectedCategories.length === 0 || (result.categories?.some(cat => selectedCategories.includes(cat)));
        return percentage >= percentageThreshold && categoryMatch;
    });

    console.log('Filtered Resumes for Shortlisting:', filteredResumes);

    try {
        const response = await axios.post('/shortlist_resumes', {
            summarized_data: filteredResumes,
            percentage_threshold: percentageThreshold,
            categories: selectedCategories
        }, {
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.data.message) {
            alert(response.data.message);
        } else {
            alert('Failed to shortlist resumes. Please check the console for details.');
        }
    } catch (err) {
        alert(`Error shortlisting resumes: ${err.response?.data?.error || 'Please try again.'}`);
        console.error('Shortlist Error:', err);
    }
};

fileInput.setAttribute('accept', SUPPORTED_EXTENSIONS.join(','));

dropzone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => {
    updateFileDisplay();
});

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
        const existingFiles = Array.from(fileInput.files);
        const newFiles = Array.from(e.dataTransfer.files);
        const combinedFiles = [...existingFiles, ...newFiles];
        
        const dt = new DataTransfer();
        combinedFiles.forEach(file => dt.items.add(file));
        
        fileInput.files = dt.files;
        updateFileDisplay();
    }
});

function updateFileDisplay() {
    const files = fileInput.files;
    fileCount.textContent = files.length > 0 ? `${files.length} file(s) selected` : 'No files selected';
    viewFilesButton.style.display = files.length > 0 ? 'inline-block' : 'none';
    if (files.length === 0) {
        document.getElementById('dropzone-text').textContent = 'Drag & drop files here or click to browse (PDF, DOCX, TXT, PNG, JPG, JPEG)';
    }
}

viewFilesButton.onclick = () => {
    const files = fileInput.files;
    modalFileList.innerHTML = '';
    if (files.length === 0) {
        modalFileList.innerHTML = '<tr><td colspan="3">No files selected.</td></tr>';
    } else {
        Array.from(files).forEach((file, index) => {
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (SUPPORTED_EXTENSIONS.includes(ext)) {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${file.name}</td>
                    <td>${(file.size / 1024).toFixed(1)}KB</td>
                    <td><button class="btn btn-sm btn-outline-danger delete-btn" data-index="${index}"><i class="fas fa-times"></i></button></td>
                `;
                modalFileList.appendChild(row);
            } else {
                alert(`File "${file.name}" is not supported. Supported types: ${SUPPORTED_EXTENSIONS.join(', ')}`);
            }
        });
    }
    new bootstrap.Modal(document.getElementById('fileModal')).show();
};

// Event delegation for delete buttons
modalFileList.addEventListener('click', (e) => {
    if (e.target.closest('.delete-btn')) {
        const index = parseInt(e.target.closest('.delete-btn').getAttribute('data-index'));
        removeFile(index);
    }
});

function removeFile(index) {
    const dt = new DataTransfer();
    const files = Array.from(fileInput.files);
    
    files.forEach((file, i) => {
        if (i !== index) dt.items.add(file);
    });
    
    fileInput.files = dt.files;
    updateFileListInModal();
    updateFileDisplay();
}

function updateFileListInModal() {
    const files = fileInput.files;
    modalFileList.innerHTML = '';
    if (files.length === 0) {
        modalFileList.innerHTML = '<tr><td colspan="3">No files selected.</td></tr>';
    } else {
        Array.from(files).forEach((file, index) => {
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (SUPPORTED_EXTENSIONS.includes(ext)) {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${file.name}</td>
                    <td>${(file.size / 1024).toFixed(1)}KB</td>
                    <td><button class="btn btn-sm btn-outline-danger delete-btn" data-index="${index}"><i class="fas fa-times"></i></button></td>
                `;
                modalFileList.appendChild(row);
            }
        });
    }
}

function displayCharts() {
    const percentageThreshold = parseFloat(percentageThresholdSelect.value) || 0;
    let dataToVisualize = categorizedResults;

    if (currentDisplayCategory) {
        dataToVisualize = { [currentDisplayCategory]: categorizedResults[currentDisplayCategory] };
    }

    if (currentAction === 'match') {
        dataToVisualize = Object.fromEntries(
            Object.entries(dataToVisualize).map(([category, resumes]) => [
                category,
                resumes.filter(resume => {
                    const percentage = parseFloat(resume.percentage_match.replace('%', '')) || 0;
                    return percentage >= percentageThreshold;
                })
            ])
        );
    }

    const categories = Object.keys(dataToVisualize);
    const counts = categories.map(category => dataToVisualize[category].length);
    const total = counts.reduce((sum, count) => sum + count, 0);
    const percentages = counts.map(count => total > 0 ? ((count / total) * 100).toFixed(1) : 0);

    if (pieChart) pieChart.destroy();
    if (barChart) barChart.destroy();

    const pieCtx = document.getElementById('pieChart').getContext('2d');
    pieChart = new Chart(pieCtx, {
        type: 'pie',
        data: {
            labels: categories,
            datasets: [{
                data: percentages,
                backgroundColor: [
                    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
                    '#FF9F40', '#C9CBCF', '#7BC043', '#F4A261', '#E76F51'
                ],
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'top' },
                title: { display: true, text: 'Percentage Distribution by Category' },
                tooltip: { callbacks: { label: context => `${context.label}: ${context.raw}%` } }
            }
        }
    });

    const barCtx = document.getElementById('barChart').getContext('2d');
    barChart = new Chart(barCtx, {
        type: 'bar',
        data: {
            labels: categories,
            datasets: [{
                label: 'Number of Resumes',
                data: counts,
                backgroundColor: '#36A2EB',
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                title: { display: true, text: 'Count of Resumes by Category' }
            },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Count' } },
                x: { title: { display: true, text: 'Category' } }
            }
        }
    });

    visualizationDiv.style.display = total > 0 ? 'block' : 'none';
}