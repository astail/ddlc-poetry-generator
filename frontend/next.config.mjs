/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // CI/build gate is type-checking; lint runs locally via `npm run lint`.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
