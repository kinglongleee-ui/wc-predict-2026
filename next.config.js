/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 适配腾讯云 Webify 部署 (output: 'standalone' 产出可独立运行的 server.js)
  output: 'standalone',
  // 把 data/ 整个目录打进 standalone output, 否则 fs.readFileSync('data/...') 读不到
  outputFileTracingIncludes: {
    '/': ['./data/**/*'],
  },
};

module.exports = nextConfig;
