document.addEventListener('DOMContentLoaded', () => {
    const navLinks = document.querySelectorAll('.nav-link');
    const navbarCollapse = document.getElementById('navbarNav');
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbar = document.querySelector('.navbar');

    let lastScroll = 0;
    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;
        if (currentScroll > lastScroll && currentScroll > 60) {
            navbar.style.transform = 'translateY(-100%)';
        } else {
            navbar.style.transform = 'translateY(0)';
        }
        lastScroll = currentScroll;
    });

    // Prevent rapid touch events on mobile
    let isToggling = false;
    navbarToggler.addEventListener('touchstart', (event) => {
        event.preventDefault();
        if (!isToggling && window.innerWidth <= 991) {
            isToggling = true;
            navbarToggler.click();
            setTimeout(() => { isToggling = false; }, 300);
        }
    });

    // Close navbar on nav link click only on mobile
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (navbarCollapse.classList.contains('show') && !isToggling && window.innerWidth <= 991) {
                isToggling = true;
                const bsCollapse = new bootstrap.Collapse(navbarCollapse, { toggle: false });
                bsCollapse.hide();
                setTimeout(() => { isToggling = false; }, 300);
            }
        });
    });

    // Initialize form elements
    const initialForm = document.getElementById('resumeForm');
    const fullForm = document.getElementById('resumeFormFull');
    const initialSection = document.getElementById('initial-section');
    const fullInterface = document.getElementById('full-interface');

    // Sync form inputs between initial and full forms
    const syncForms = (sourceForm, targetForm) => {
        const sourceJobRole = sourceForm.querySelector('#jobRole').value;
        const sourceJobDescription = sourceForm.querySelector('#jobDescription').value;
        const sourceResumes = sourceForm.querySelector('#resumes').files;

        targetForm.querySelector('#jobRole').value = sourceJobRole;
        targetForm.querySelector('#jobDescription').value = sourceJobDescription;

        // Update file input and UI for target form
        const targetFileInput = targetForm.querySelector('#resumes');
        const targetFileCount = targetForm.querySelector('#file-count');
        const targetViewFilesButton = targetForm.querySelector('#viewFilesButton');

        // Create a new DataTransfer to assign files
        const dataTransfer = new DataTransfer();
        Array.from(sourceResumes).forEach(file => dataTransfer.items.add(file));
        targetFileInput.files = dataTransfer.files;

        // Update file display for target form
        updateFileDisplay(targetFileInput, targetFileCount, targetViewFilesButton);
    };

    // Attach event listeners to both forms
    [initialForm, fullForm].forEach(form => {
        const summarizeButton = form.querySelector('#summarizeButton');
        const matchButton = form.querySelector('#matchButton');
        const generateJDButton = form.querySelector('#generateJD');
        const dropzone = form.querySelector('#dropzone');
        const fileInput = form.querySelector('#resumes');
        const fileCount = form.querySelector('#file-count');
        const viewFilesButton = form.querySelector('#viewFilesButton');

        summarizeButton.onclick = () => {
            syncForms(form, form === initialForm ? fullForm : initialForm);
            submitForm('summarize', form);
        };

        matchButton.onclick = () => {
            const jobDescription = form.querySelector('#jobDescription').value.trim();
            if (!jobDescription) {
                alert('Please provide a job description to perform percentage match.');
                return;
            }
            syncForms(form, form === initialForm ? fullForm : initialForm);
            submitForm('match', form);
        };

        generateJDButton.onclick = async () => {
            const jobRole = form.querySelector('#jobRole').value.trim();
            if (!jobRole) {
                alert("Please enter a job role.");
                return;
            }

            try {
                form.querySelector('#jobDescription').placeholder = "Generating JD...";
                const response = await axios.post('/generate_jd',
                    { job_role: jobRole },
                    { headers: { 'Content-Type': 'application/json' } }
                );

                if (response.data.job_description) {
                    form.querySelector('#jobDescription').value = response.data.job_description;
                    syncForms(form, form === initialForm ? fullForm : initialForm);
                } else {
                    alert("Failed to generate JD. Try again.");
                }
            } catch (error) {
                alert("Error fetching JD: Check the console for details.");
            } finally {
                form.querySelector('#jobDescription').placeholder = "Enter the job description here...";
            }
        };

        dropzone.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', () => {
            updateFileDisplay(fileInput, fileCount, viewFilesButton);
            syncForms(form, form === initialForm ? fullForm : initialForm);
        });

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });

        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('dragover');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            fileInput.files = files;
            updateFileDisplay(fileInput, fileCount, viewFilesButton);
            syncForms(form, form === initialForm ? fullForm : initialForm);
        });

        viewFilesButton.onclick = () => {
            updateModalFileList(fileInput);
            const fileModal = new bootstrap.Modal(document.getElementById('fileModal'), { centered: true });
            fileModal.show();
        };
    });
});

const axios = window.axios || (function() { throw new Error('Axios is not loaded. Please include axios.js'); })();

const SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.png', '.jpg', '.jpeg'];

let summarizedData = [];
let matchData = [];
let categorizedResults = {};
let currentAction = '';
let currentDisplayCategory = '';
let countdownInterval;
let pieChart, barChart;
let progressInterval;

const submitForm = async (action, form) => {
    const formData = new FormData(form);
    formData.append('action', action);
    currentAction = action;

    const isInitialForm = form.id === 'resumeForm';
    const initialProgress = document.getElementById('initialProgress');
    const initialProgressBar = document.getElementById('initialProgressBar');
    const initialProgressText = document.getElementById('initialProgressText');
    const loader = document.getElementById('loader');
    const timeRemainingElement = document.getElementById('timeRemaining');
    const resultsDiv = document.getElementById('results');
    const downloadCsvButton = document.getElementById('downloadCsvButton');
    const downloadFilteredCsvButton = document.getElementById('downloadFilteredCsvButton');
    const shortlistButton = document.getElementById('shortlistButton');
    const categoryFilters = document.getElementById('categoryFilters');
    const visualizationDiv = document.getElementById('visualization');
    const initialSection = document.getElementById('initial-section');
    const fullInterface = document.getElementById('full-interface');

    // Show progress bar for initial form, loader for full form
    if (isInitialForm && initialProgress && initialProgressBar && initialProgressText) {
        initialProgress.style.display = 'block';
        initialProgressBar.style.width = '0%';
        initialProgressBar.setAttribute('aria-valuenow', '0');
        initialProgressText.textContent = 'Processing resumes...';
    } else {
        loader.style.display = 'block';
    }

    downloadCsvButton.style.display = 'none';
    downloadFilteredCsvButton.style.display = 'none';
    shortlistButton.style.display = 'none';
    categoryFilters.style.display = 'none';
    visualizationDiv.style.display = 'none';
    resultsDiv.innerHTML = '';

    const numberOfResumes = formData.getAll('resumes').length;
    let estimatedTime = action === 'summarize' ? numberOfResumes * 5 : numberOfResumes * 4;

    // Animate progress bar for initial form
    if (isInitialForm && initialProgress && initialProgressBar) {
        let progress = 0;
        const increment = 100 / (estimatedTime * 1000 / 50); // Update every 50ms
        progressInterval = setInterval(() => {
            progress = Math.min(progress + increment, 100);
            initialProgressBar.style.width = `${progress}%`;
            initialProgressBar.setAttribute('aria-valuenow', progress.toFixed(0));
            if (progress >= 100) {
                clearInterval(progressInterval);
                initialProgressText.textContent = 'Finalizing...';
            }
        }, 50);
    }

    startCountdown(estimatedTime);

    try {
        const response = await axios.post('/process_resumes', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });

        // Show full interface
        initialSection.style.display = 'none';
        fullInterface.style.display = 'block';

        const data = response.data;
        const results = data.results || [];
        categorizedResults = data.categorized_results || {};

        if (action === 'summarize') {
            summarizedData = results;
        } else if (action === 'match') {
            matchData = results;
        }

        displayResults(results, action, currentDisplayCategory);
        categoryFilters.style.display = 'block';
        downloadCsvButton.style.display = 'inline-block';
        downloadFilteredCsvButton.style.display = 'inline-block';
        if (action === 'match') {
            shortlistButton.style.display = 'inline-block';
        }

        setupCategoryFilters();
        setupPercentageFilter();
        displayCharts();
    } catch (err) {
        const errorMessage = err.response?.data?.error || 'Error processing resumes. Please try again.';
        alert(errorMessage);
    } finally {
        // Clean up
        if (isInitialForm && initialProgress) {
            initialProgress.style.display = 'none';
            clearInterval(progressInterval);
        }
        loader.style.display = 'none';
        clearInterval(countdownInterval);
        timeRemainingElement.innerHTML = 'Processing complete!';
    }
};

const startCountdown = (timeInSeconds) => {
    let timeLeft = timeInSeconds;
    const timeRemainingElement = document.getElementById('timeRemaining');
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
    const percentageThresholdSelect = document.getElementById('percentageThreshold');
    const resultsDiv = document.getElementById('results');
    const percentageThreshold = parseFloat(percentageThresholdSelect.value) || 0;
    let filteredResults = results;

    if (action === 'match' && percentageThreshold > 0) {
        filteredResults = results.filter(result => {
            const percentage = parseFloat(result.percentage_match.replace('%', '')) || 0;
            return percentage >= percentageThreshold;
        });
    }

    if (displayCategory && categorizedResults[displayCategory]) {
        filteredResults = filteredResults.filter(result =>
            result.categories?.includes(displayCategory) || (!result.categories && displayCategory === 'Uncategorized')
        );
    }

    if (action === 'match') {
        filteredResults.sort((a, b) => {
            let percentA = parseFloat(a.percentage_match.replace('%', '')) || 0;
            let percentB = parseFloat(b.percentage_match.replace('%', '')) || 0;
            return percentB - percentA;
        });
    }

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
            currentDisplayCategory = button.getAttribute('data-category');
            buttons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            if (currentDisplayCategory) {
                const filteredResults = categorizedResults[currentDisplayCategory] || [];
                displayResults(currentAction === 'summarize' ? summarizedData : matchData, currentAction, currentDisplayCategory);
            } else {
                displayResults(currentAction === 'summarize' ? summarizedData : matchData, currentAction, '');
            }
            displayCharts();
        };
    });
};

const setupPercentageFilter = () => {
    const percentageThresholdSelect = document.getElementById('percentageThreshold');
    percentageThresholdSelect.onchange = () => {
        displayResults(currentAction === 'summarize' ? summarizedData : matchData, currentAction, currentDisplayCategory);
        displayCharts();
    };
};

const downloadCsvButton = document.getElementById('downloadCsvButton');
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

const downloadFilteredCsvButton = document.getElementById('downloadFilteredCsvButton');
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

const shortlistButton = document.getElementById('shortlistButton');
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

const updateFileDisplay = (fileInput, fileCount, viewFilesButton) => {
    const files = fileInput.files;
    fileCount.textContent = `${files.length} file${files.length !== 1 ? 's' : ''} selected`;
    viewFilesButton.style.display = files.length > 0 ? 'inline-block' : 'none';
};

const updateModalFileList = (fileInput) => {
    const modalFileList = document.getElementById('modalFileList');
    if (!modalFileList) {
        console.error('modalFileList element not found');
        return;
    }
    modalFileList.innerHTML = '';
    const files = fileInput.files;
    Array.from(files).forEach((file, index) => {
        if (SUPPORTED_EXTENSIONS.some(ext => file.name.toLowerCase().endsWith(ext))) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${file.name}</td>
                <td>${(file.size / 1024).toFixed(2)} KB</td>
                <td><button class="btn btn-danger btn-sm remove-file" data-index="${index}">Remove</button></td>
            `;
            modalFileList.appendChild(row);
        }
    });

    document.querySelectorAll('.remove-file').forEach(button => {
        button.onclick = (e) => {
            const index = parseInt(e.target.getAttribute('data-index'));
            const dataTransfer = new DataTransfer();
            Array.from(fileInput.files).forEach((file, i) => {
                if (i !== index) dataTransfer.items.add(file);
            });
            fileInput.files = dataTransfer.files;
            updateFileDisplay(fileInput, document.getElementById('file-count'), document.getElementById('viewFilesButton'));
            updateModalFileList(fileInput);
            modalFileList.focus();
        };
    });
};

const updateSelectedCategoriesDisplay = () => {
    const selectedCategoriesDisplay = document.getElementById('selectedCategories');
    const selectedCategories = Array.from(document.querySelectorAll('.category-checkbox:checked'))
        .map(checkbox => checkbox.value);
    selectedCategoriesDisplay.textContent = `Selected categories: ${selectedCategories.length > 0 ? selectedCategories.join(', ') : 'None'}`;
};

document.getElementById('categoryModalButton').onclick = () => {
    const fileModal = bootstrap.Modal.getInstance(document.getElementById('fileModal'));
    if (fileModal) fileModal.hide();
};

document.getElementById('saveCategories').onclick = () => {
    updateSelectedCategoriesDisplay();
};

document.querySelectorAll('.category-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', updateSelectedCategoriesDisplay);
});

const displayCharts = () => {
    const percentageThresholdSelect = document.getElementById('percentageThreshold');
    const visualizationDiv = document.getElementById('visualization');
    const percentageThreshold = parseFloat(percentageThresholdSelect.value) || 0;
    let filteredResults = currentAction === 'summarize' ? summarizedData : matchData;

    if (currentAction === 'match' && percentageThreshold > 0) {
        filteredResults = filteredResults.filter(result => {
            const percentage = parseFloat(result.percentage_match.replace('%', '')) || 0;
            return percentage >= percentageThreshold;
        });
    }

    if (currentDisplayCategory && categorizedResults[currentDisplayCategory]) {
        filteredResults = filteredResults.filter(result =>
            result.categories?.includes(currentDisplayCategory) || (!result.categories && currentDisplayCategory === 'Uncategorized')
        );
    }

    const categoryCounts = {};
    filteredResults.forEach(result => {
        const categories = result.categories || ['Uncategorized'];
        categories.forEach(category => {
            categoryCounts[category] = (categoryCounts[category] || 0) + 1;
        });
    });

    const labels = Object.keys(categoryCounts);
    const data = Object.values(categoryCounts);

    visualizationDiv.style.display = 'block';

    if (pieChart) pieChart.destroy();
    if (barChart) barChart.destroy();

    const pieCtx = document.getElementById('pieChart').getContext('2d');
    pieChart = new Chart(pieCtx, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
                    '#FF9F40', '#66BB6A', '#EF5350', '#29B6F6', '#AB47BC'
                ],
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'top' },
                title: { display: true, text: 'Category Distribution (Pie)' }
            }
        }
    });

    const barCtx = document.getElementById('barChart').getContext('2d');
    barChart = new Chart(barCtx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Number of Resumes',
                data: data,
                backgroundColor: '#36A2EB',
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                title: { display: true, text: 'Category Distribution (Bar)' }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
};