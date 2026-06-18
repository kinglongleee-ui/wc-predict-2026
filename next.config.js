/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow serving JSON data files from /data/runs/ at build time
  // (Next.js bundles anything inside the project; data/ is included automatically)
};

module.exports = nextConfig;
