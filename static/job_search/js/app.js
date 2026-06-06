document.addEventListener("DOMContentLoaded", () => {
    // Particle Canvas Animation
    initParticles();
    initCounter();
    startLiveTime();

    const uploadArea = document.getElementById("uploadArea");
    const resumeInput = document.getElementById("resumeInput");
    const fileSelected = document.getElementById("fileSelected");
    const fileName = document.getElementById("fileName");
    const removeFile = document.getElementById("removeFile");
    const analyzeBtn = document.getElementById("analyzeBtn");
    const profileSection = document.getElementById("profileSection");
    const profileSummary = document.getElementById("profileSummary");
    const skillsContainer = document.getElementById("skillsContainer");
    const suggestedRoles = document.getElementById("suggestedRoles");
    const locationInput = document.getElementById("locationInput");
    const searchBtn = document.getElementById("searchBtn");
    const resultsSection = document.getElementById("resultsSection");
    const emptyState = document.getElementById("emptyState");
    const jobsGrid = document.getElementById("jobsGrid");
    const resultCount = document.getElementById("resultCount");
    const resultsTitle = document.getElementById("resultsTitle");
    const filterTabs = document.getElementById("filterTabs");

    let selectedFile = null;
    let resumeProfile = null;
    let allJobs = [];
    let searchMode = "both";

    // Mode selector
    document.querySelectorAll(".mode-card").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".mode-card").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            searchMode = tab.dataset.mode;
            updateSearchButtonText();
            updateFilterVisibility();
        });
    });

    function updateSearchButtonText() {
        const btnText = searchBtn.querySelector(".btn-text");
        const labels = {
            jobs: "Find Matching Jobs",
            freelance: "Find Freelance Gigs",
            clients: "Find Potential Clients",
            influencers: "Find Influencers",
            sponsors: "Find Sponsors & Brand Deals",
            both: "Find All Opportunities"
        };
        btnText.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="13 17 18 12 13 7"></polyline>
                <polyline points="6 17 11 12 6 7"></polyline>
            </svg>
            ${labels[searchMode] || labels.both}
        `;
    }

    function updateFilterVisibility() {
        document.querySelectorAll(".job-filter").forEach(tab => {
            tab.style.display = (searchMode === "jobs" || searchMode === "both") ? "" : "none";
        });
        document.querySelectorAll(".freelance-filter").forEach(tab => {
            tab.style.display = (searchMode === "freelance" || searchMode === "both") ? "" : "none";
        });
        document.querySelectorAll(".client-filter").forEach(tab => {
            tab.style.display = (searchMode === "clients") ? "" : "none";
        });
        document.querySelectorAll(".influencer-filter").forEach(tab => {
            tab.style.display = (searchMode === "influencers") ? "" : "none";
        });
        document.querySelectorAll(".sponsor-filter").forEach(tab => {
            tab.style.display = (searchMode === "sponsors") ? "" : "none";
        });
    }

    updateFilterVisibility();

    // Upload area events
    uploadArea.addEventListener("click", () => resumeInput.click());

    uploadArea.addEventListener("dragover", (e) => {
        e.preventDefault();
        uploadArea.classList.add("dragover");
    });

    uploadArea.addEventListener("dragleave", () => {
        uploadArea.classList.remove("dragover");
    });

    uploadArea.addEventListener("drop", (e) => {
        e.preventDefault();
        uploadArea.classList.remove("dragover");
        const files = e.dataTransfer.files;
        if (files.length > 0) handleFileSelect(files[0]);
    });

    resumeInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) handleFileSelect(e.target.files[0]);
    });

    removeFile.addEventListener("click", () => {
        selectedFile = null;
        resumeInput.value = "";
        uploadArea.style.display = "block";
        fileSelected.style.display = "none";
        analyzeBtn.disabled = true;
    });

    analyzeBtn.addEventListener("click", analyzeResume);
    searchBtn.addEventListener("click", searchJobs);

    filterTabs.addEventListener("click", (e) => {
        if (e.target.classList.contains("filter-chip")) {
            document.querySelectorAll(".filter-chip").forEach(tab => tab.classList.remove("active"));
            e.target.classList.add("active");
            filterJobs(e.target.dataset.source);
        }
    });

    function handleFileSelect(file) {
        const validExts = [".pdf", ".docx", ".doc", ".txt"];
        const ext = "." + file.name.split(".").pop().toLowerCase();

        if (!validExts.includes(ext)) {
            showToast("Please upload a PDF, DOCX, or TXT file.", "error");
            return;
        }

        selectedFile = file;
        fileName.textContent = file.name;
        uploadArea.style.display = "none";
        fileSelected.style.display = "block";
        analyzeBtn.disabled = false;
    }

    async function analyzeResume() {
        if (!selectedFile) return;

        if (selectedFile.size > 10 * 1024 * 1024) {
            showToast("Please upload a file smaller than 10MB.", "error");
            return;
        }

        setButtonLoading(analyzeBtn, true);

        const formData = new FormData();
        formData.append("resume", selectedFile);

        try {
            const response = await fetch("/api/analyze-resume", {
                method: "POST",
                body: formData,
            });

            let data;
            try {
                data = await response.json();
            } catch (parseError) {
                throw new Error("Failed to parse server response");
            }

            if (response.ok && data.success) {
                resumeProfile = data.profile;
                showProfile(resumeProfile);
            } else {
                showToast(data.error || "Failed to analyze resume.", "error");
            }
        } catch (error) {
            showToast(error.message || "Failed to analyze resume. Check your connection.", "error");
        } finally {
            setButtonLoading(analyzeBtn, false);
        }
    }

    function showProfile(profile) {
        profileSection.style.display = "block";
        profileSection.scrollIntoView({ behavior: "smooth", block: "start" });

        profileSummary.innerHTML = `<p>${profile.summary}</p>`;

        let skillsHTML = "";
        const categoryNames = {
            programming: "Programming Languages",
            frameworks: "Frameworks & Libraries",
            data: "Data & AI",
            cloud_devops: "Cloud & DevOps",
            databases: "Databases",
            roles: "Roles & Expertise",
            soft_skills: "Soft Skills",
        };

        for (const [category, skills] of Object.entries(profile.skills)) {
            if (skills.length > 0) {
                skillsHTML += `
                    <div class="skills-category">
                        <h4>${categoryNames[category] || category}</h4>
                        <div class="skills-tags">
                            ${skills.map(s => `<span class="skill-tag">${s}</span>`).join("")}
                        </div>
                    </div>
                `;
            }
        }
        skillsContainer.innerHTML = skillsHTML;

        suggestedRoles.innerHTML = profile.suggested_titles
            .map(title => `<span class="role-tag">${title}</span>`)
            .join("");
    }

    async function searchJobs() {
        if (!resumeProfile) return;

        const location = locationInput.value.trim();
        setButtonLoading(searchBtn, true);
        resultsSection.style.display = "none";
        emptyState.style.display = "none";

        try {
            const response = await fetch("/api/search", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    queries: resumeProfile.suggested_titles,
                    location: location,
                    resume_skills: resumeProfile.all_skills,
                    suggested_titles: resumeProfile.suggested_titles,
                    mode: searchMode,
                }),
            });

            const data = await response.json();

            if (response.ok) {
                allJobs = data.jobs;

                const titles = {
                    jobs: "Jobs Matching Your Profile",
                    freelance: "Freelance Gigs for Your Skills",
                    clients: "Potential Clients for You",
                    influencers: "Influencers in Your Niche",
                    sponsors: "Sponsorship Opportunities",
                    both: "All Opportunities Matched"
                };

                let titleText = titles[searchMode] || titles.both;
                if (location) titleText += ` in ${location}`;
                resultsTitle.textContent = titleText;

                const countLabels = {
                    clients: "client leads",
                    influencers: "influencers",
                    sponsors: "sponsorship opportunities"
                };
                resultCount.textContent = `${data.total} ${countLabels[searchMode] || "opportunities"} found across ${searchMode === "both" ? "10" : "5"}+ platforms`;

                if (allJobs.length > 0) {
                    renderJobs(allJobs);
                    resultsSection.style.display = "block";
                    updateFilterVisibility();
                    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
                } else {
                    emptyState.style.display = "block";
                }

                document.querySelectorAll(".filter-chip").forEach(tab => tab.classList.remove("active"));
                document.querySelector('[data-source="all"]').classList.add("active");
            } else {
                showToast(data.error || "Search failed. Please try again.", "error");
            }
        } catch (error) {
            showToast("Failed to search. Check your connection.", "error");
        } finally {
            setButtonLoading(searchBtn, false);
        }
    }

    function filterJobs(source) {
        if (source === "all") {
            renderJobs(allJobs);
            resultCount.textContent = `${allJobs.length} opportunities found`;
        } else {
            const filtered = allJobs.filter(job => job.source === source);
            renderJobs(filtered);
            resultCount.textContent = `${filtered.length} results from ${source}`;
        }
    }

    function renderJobs(jobs) {
        jobsGrid.innerHTML = jobs.map(job => createJobCard(job)).join("");
    }

    function createJobCard(job) {
        const sourceClass = getSourceClass(job.source);
        const isFreelance = job.type === "freelance";
        const isClient = job.type === "client";
        const isInfluencer = job.type === "influencer";
        const isSponsor = job.type === "sponsor";
        const matchScore = job.match_score || 0;

        let matchBadge = "";
        if (matchScore >= 20) {
            matchBadge = `<span class="match-badge high">High Match</span>`;
        } else if (matchScore >= 10) {
            matchBadge = `<span class="match-badge">Good Match</span>`;
        }

        let typeBadge = "";
        if (isFreelance) typeBadge = `<span class="type-badge freelance-badge">Freelance</span>`;
        else if (isClient) typeBadge = `<span class="type-badge client-badge">Client Lead</span>`;
        else if (isInfluencer) typeBadge = `<span class="type-badge influencer-badge">Influencer</span>`;
        else if (isSponsor) typeBadge = `<span class="type-badge sponsor-badge">Sponsorship</span>`;

        const description = job.description ? `<p class="job-description">${escapeHtml(job.description)}</p>` : "";

        const applyTexts = { freelance: "View Project", client: "View Lead", influencer: "View Profile", sponsor: "View Opportunity" };
        let applyText = applyTexts[job.type] || "Apply Now";

        let cardClass = "";
        if (isFreelance) cardClass = "freelance-card";
        else if (isClient) cardClass = "client-card";
        else if (isInfluencer) cardClass = "influencer-card";
        else if (isSponsor) cardClass = "sponsor-card";

        let applyClass = "apply-btn";
        if (isFreelance) applyClass += " freelance-apply";
        else if (isClient) applyClass += " client-apply";
        else if (isInfluencer) applyClass += " influencer-apply";
        else if (isSponsor) applyClass += " sponsor-apply";

        let companyIcon = '<path d="M3 21h18M3 7v14M21 7v14M6 11h.01M6 15h.01M6 19h.01M10 11h.01M10 15h.01M10 19h.01M14 11h.01M14 15h.01M14 19h.01M18 11h.01M18 15h.01M18 19h.01M3 7l9-4 9 4"></path>';
        if (isFreelance) companyIcon = '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle>';
        else if (isClient) companyIcon = '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path>';
        else if (isInfluencer) companyIcon = '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path>';
        else if (isSponsor) companyIcon = '<rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect><line x1="1" y1="10" x2="23" y2="10"></line>';

        return `
            <div class="job-card ${cardClass}">
                <div class="job-card-header">
                    <h3 class="job-title">${escapeHtml(job.title)}</h3>
                    <span class="source-badge ${sourceClass}">${escapeHtml(job.source)}</span>
                </div>
                <div class="badges-row">
                    ${matchBadge}
                    ${typeBadge}
                </div>
                ${job.company ? `
                <div class="job-company">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${companyIcon}</svg>
                    <span>${escapeHtml(job.company)}</span>
                </div>` : ""}
                ${job.location ? `
                <div class="job-location">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                        <circle cx="12" cy="10" r="3"></circle>
                    </svg>
                    <span>${escapeHtml(job.location)}</span>
                </div>` : ""}
                ${description}
                <a href="${escapeHtml(job.apply_link)}" target="_blank" rel="noopener noreferrer" class="${applyClass}">
                    ${applyText}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                        <polyline points="15 3 21 3 21 9"></polyline>
                        <line x1="10" y1="14" x2="21" y2="3"></line>
                    </svg>
                </a>
            </div>
        `;
    }

    function getSourceClass(source) {
        const classes = {
            "Google Jobs": "google", "LinkedIn": "linkedin", "Indeed": "indeed",
            "Glassdoor": "glassdoor", "RemoteOK": "remoteok", "Upwork": "upwork",
            "Freelancer": "freelancer", "Fiverr": "fiverr", "Toptal": "toptal",
            "Guru": "guru", "AngelList": "angellist", "ProductHunt": "producthunt",
            "Craigslist": "craigslist", "PeoplePerHour": "peopleperhour",
            "Contra": "contra", "99designs": "ninetynindesigns", "YouTube": "youtube",
            "TikTok": "tiktok", "Instagram": "instagram", "IMHub": "imhub",
            "Heepsy": "heepsy", "Upfluence": "upfluence", "Collabstr": "collabstr",
            "SponsorSearch": "sponsorsearch", "Grapevine": "grapevine",
            "Aspire": "aspire", "Brandbassador": "brandbassador", "IZEA": "izea",
            "HashtagPaid": "hashtagpaid", "BrandConnect": "brandconnect",
            "SponsorGap": "sponsorgap",
        };
        return classes[source] || "";
    }

    function setButtonLoading(btn, loading) {
        const text = btn.querySelector(".btn-text");
        const loader = btn.querySelector(".btn-loader");
        btn.disabled = loading;
        text.style.display = loading ? "none" : "inline-flex";
        loader.style.display = loading ? "inline-flex" : "none";
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.style.cssText = `
            position: fixed; bottom: 2rem; right: 2rem; z-index: 9999;
            padding: 1rem 1.5rem; border-radius: 12px; font-size: 0.9rem;
            font-weight: 500; color: white; max-width: 400px;
            backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1);
            animation: slideUp 0.3s ease-out;
            background: ${type === "error" ? "rgba(239, 68, 68, 0.9)" : "rgba(99, 102, 241, 0.9)"};
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        `;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(10px)";
            toast.style.transition = "all 0.3s";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // Particle System
    function initParticles() {
        const canvas = document.getElementById("particleCanvas");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");

        function resize() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
        resize();
        window.addEventListener("resize", resize);

        const particles = [];
        const count = Math.min(80, Math.floor(window.innerWidth / 20));

        for (let i = 0; i < count; i++) {
            particles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * 0.4,
                vy: (Math.random() - 0.5) * 0.4,
                radius: Math.random() * 1.5 + 0.5,
                opacity: Math.random() * 0.3 + 0.1,
            });
        }

        function animate() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            particles.forEach((p, i) => {
                p.x += p.vx;
                p.y += p.vy;

                if (p.x < 0) p.x = canvas.width;
                if (p.x > canvas.width) p.x = 0;
                if (p.y < 0) p.y = canvas.height;
                if (p.y > canvas.height) p.y = 0;

                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(99, 102, 241, ${p.opacity})`;
                ctx.fill();

                for (let j = i + 1; j < particles.length; j++) {
                    const dx = particles[j].x - p.x;
                    const dy = particles[j].y - p.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < 120) {
                        ctx.beginPath();
                        ctx.moveTo(p.x, p.y);
                        ctx.lineTo(particles[j].x, particles[j].y);
                        ctx.strokeStyle = `rgba(99, 102, 241, ${0.08 * (1 - dist / 120)})`;
                        ctx.lineWidth = 0.5;
                        ctx.stroke();
                    }
                }
            });

            requestAnimationFrame(animate);
        }
        animate();
    }

    // Counter Animation
    function initCounter() {
        const counters = document.querySelectorAll(".counter");
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const el = entry.target;
                    const target = parseInt(el.dataset.target);
                    animateCounter(el, 0, target, 2000);
                    observer.unobserve(el);
                }
            });
        });
        counters.forEach(c => observer.observe(c));
    }

    function startLiveTime() {
        const liveTimeEl = document.getElementById("liveTime");
        if (!liveTimeEl) return;

        function updateTime() {
            const now = new Date();
            const timeString = now.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
            });
            liveTimeEl.textContent = timeString;
        }

        updateTime();
        setInterval(updateTime, 1000);
    }

    function animateCounter(el, start, end, duration) {
        const startTime = performance.now();
        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.floor(start + (end - start) * eased);
            if (progress < 1) requestAnimationFrame(update);
        }
        requestAnimationFrame(update);
    }
});

// Add slideUp animation
const style = document.createElement("style");
style.textContent = `@keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }`;
document.head.appendChild(style);
