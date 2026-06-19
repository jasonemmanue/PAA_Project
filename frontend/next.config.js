/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // L'i18n est gérée côté client (provider React), pas par les routes Next.js,
  // ce qui permet la bascule instantanée FR/EN sans rechargement de page.
};

module.exports = nextConfig;
