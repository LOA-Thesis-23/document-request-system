function validatePasswords() {
    const pw = document.getElementById('reg-password').value;
    const confirm = document.getElementById('confirm_password').value;
    if (pw !== confirm) {
        alert('Passwords do not match.');
        return false;
    }
    return true;
}