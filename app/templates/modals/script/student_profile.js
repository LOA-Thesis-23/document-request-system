(function() {
    const editBtn = document.getElementById('edit-profile-btn');
    const cancelBtn = document.getElementById('cancel-edit-btn');
    const actions = document.getElementById('profile-form-actions');
    const editableFields = ['full_name', 'email'];

    editBtn.addEventListener('click', () => {
        editableFields.forEach(id => document.getElementById(id).disabled = false);
        actions.style.display = 'block';
        editBtn.style.display = 'none';
    });

    cancelBtn.addEventListener('click', () => {
        editableFields.forEach(id => document.getElementById(id).disabled = true);
        actions.style.display = 'none';
        editBtn.style.display = 'inline-block';
    });
})();