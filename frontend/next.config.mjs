/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Next 16 removed build-time ESLint integration (and `next lint`); linting is
  // a separate step (`npm run lint` -> `eslint .`, run in CI).
};

export default nextConfig;
