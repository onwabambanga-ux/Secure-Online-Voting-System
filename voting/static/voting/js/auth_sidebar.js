document.addEventListener('DOMContentLoaded', function() {
  const root = document.documentElement;
  const page = document.body;
  const toggle = document.querySelector('.sidebar-toggle');
  const sidebar = document.querySelector('.auth-sidebar');
  const backdrop = document.querySelector('.sidebar-backdrop');
  const themeButtons = document.querySelectorAll('.theme-toggle, .home-theme-toggle');
  const storedTheme = localStorage.getItem('voting-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initialTheme = storedTheme || (prefersDark ? 'dark' : 'light');

  function applyTheme(theme) {
    root.dataset.theme = theme;

    themeButtons.forEach(function(button) {
      const isDark = theme === 'dark';
      button.setAttribute('aria-pressed', String(isDark));
      button.setAttribute(
        'aria-label',
        isDark ? 'Switch to light mode' : 'Switch to dark mode'
      );

      const label = button.querySelector('.theme-toggle-label');

      if (label) {
        label.textContent = isDark ? 'Light mode' : 'Dark mode';
      }
    });
  }

  function setSidebarOpen(isOpen) {
    page.classList.toggle('sidebar-open', isOpen);

    if (toggle) {
      toggle.setAttribute('aria-expanded', String(isOpen));
      toggle.setAttribute(
        'aria-label',
        isOpen ? 'Close navigation menu' : 'Open navigation menu'
      );
    }

    if (sidebar) {
      sidebar.setAttribute('aria-hidden', String(!isOpen));
    }
  }

  applyTheme(initialTheme);
  setSidebarOpen(false);

  if (toggle) {
    toggle.addEventListener('click', function() {
      const isOpen = page.classList.contains('sidebar-open');
      setSidebarOpen(!isOpen);
    });
  }

  if (backdrop) {
    backdrop.addEventListener('click', function() {
      setSidebarOpen(false);
    });
  }

  document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
      setSidebarOpen(false);
    }
  });

  themeButtons.forEach(function(button) {
    button.addEventListener('click', function() {
      const nextTheme = root.dataset.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('voting-theme', nextTheme);
      applyTheme(nextTheme);
    });
  });

  document.querySelectorAll('.auth-sidebar a').forEach(function(link) {
    link.addEventListener('click', function() {
      setSidebarOpen(false);
    });
  });
});
