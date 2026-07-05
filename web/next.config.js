/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'export',
  // A second dev/verify server must not share .next with the primary dev
  // server (concurrent builds corrupt each other). Default stays .next.
  distDir: process.env.NEXT_DIST_DIR || '.next',
}

module.exports = nextConfig
