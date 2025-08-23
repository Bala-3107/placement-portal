document.addEventListener('DOMContentLoaded', function() {
    const toggle = document.getElementById('darkModeToggle');
    toggle.addEventListener('click', function() {
        document.body.classList.toggle('dark-mode');
    });
});
