
function openConfirmationModal(message, url) {
    document.getElementById('modal-message').innerHTML = message;
    document.getElementById('callback-url').value = url;
    //document.getElementById('modal-default').classList.add('show');
}

document.getElementById('confirm-delete-btn').addEventListener('click', function () {
    var callbackUrl = document.getElementById('callback-url').value;
    var xhr = new XMLHttpRequest();
    xhr.open('POST', callbackUrl);
    xhr.onload = function () {
        if (xhr.status === 200) {
            window.location.reload();
        } else {
            alert('Error occurred during deletion. Please try again.');
        }
    };
    xhr.send();
});

// function toggleMenu() {
//     var navbarCollapse = document.querySelector('.navbar-collapse');
//     navbarCollapse.style.display = navbarCollapse.style.display === 'block' ? 'none' : 'block';
// }

// function toggleDropdown(dropdownId) {
//     var dropdownMenu = document.getElementById(dropdownId);
//     dropdownMenu.style.display = dropdownMenu.style.display === 'block' ? 'none' : 'block';
// }


window.addEventListener('resize', function() {
  if (window.innerWidth < 768) { // Adjust breakpoint as needed
    // Expand all menus
    var navItems = document.querySelectorAll('.navbar-collapse .dropdown');
    navItems.forEach(item => {
      item.classList.add('show'); // Add Bootstrap's 'show' class
      item.querySelector('.dropdown-menu').classList.add('show');
    });

    // Disable collapse functionality
    // var collapseToggles = document.querySelectorAll('[data-bs-toggle="collapse"]');
    // collapseToggles.forEach(toggle => {
    //     toggle.setAttribute('disabled', true);
    // });
  } else {
    // Restore default behavior (if desired)
    var navItems = document.querySelectorAll('.navbar-collapse .dropdown');
    navItems.forEach(item => {
      item.classList.remove('show'); 
      item.querySelector('.dropdown-menu').classList.remove('show');
    });

    // var collapseToggles = document.querySelectorAll('[data-bs-toggle="collapse"]');
    // collapseToggles.forEach(toggle => {
    //     toggle.removeAttribute('disabled');
    // });
  }
});
