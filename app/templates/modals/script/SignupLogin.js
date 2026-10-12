    function showSignup() {
        document.getElementById('login-view').style.display = 'none';
        document.getElementById('signup-view').style.display = 'block';
    }
    function showLogin() {
        document.getElementById('signup-view').style.display = 'none';
        document.getElementById('login-view').style.display = 'block';
    }

function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    const eyeIcon = btn.querySelector('.eye-icon');
    const eyeOffIcon = btn.querySelector('.eye-off-icon');

    if (input.type === 'password') {
        input.type = 'text';
        eyeIcon.style.display = 'none';
        eyeOffIcon.style.display = 'block';
    } else {
        input.type = 'password';
        eyeIcon.style.display = 'block';
        eyeOffIcon.style.display = 'none';
    }
}