function renderNavbar(active) {
  const root = document.getElementById('navbar-root');
  if (!root) return;

  const links = [
    { key: 'beranda',      label: 'Beranda',      href: 'index.html' },
    { key: 'buat-jadwal',  label: 'Buat Jadwal',  href: 'input.html' },
    { key: 'riwayat',      label: 'Riwayat',      href: 'riwayat.html' },
  ];

  root.innerHTML = `
    <nav class="cs-navbar">
      <div class="cs-navbar-inner">
        <a href="index.html" class="cs-navbar-brand">ChronoStudy</a>
        <div class="cs-navbar-links">
          ${links.map(l => `<a href="${l.href}" class="cs-navbar-link ${active === l.key ? 'active' : ''}">${l.label}</a>`).join('')}
          <button class="cs-navbar-logout" onclick="logout()">Keluar</button>
        </div>
      </div>
    </nav>
  `;
}