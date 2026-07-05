// Flat config (ESLint 9+). Next 16 removed `next lint` and ships its shareable
// config as a native flat-config array, so we spread it directly (the old
// `.eslintrc.json` extended "next/core-web-vitals").
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = [
  ...nextCoreWebVitals,
  { ignores: [".next/**", "node_modules/**"] },
];

export default eslintConfig;
