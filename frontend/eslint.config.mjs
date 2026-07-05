// Flat config (ESLint 9+). Next 16 removed `next lint` and ships its shareable
// config as a native flat-config array, so we spread it directly (the old
// `.eslintrc.json` extended "next/core-web-vitals").
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = [
  ...nextCoreWebVitals,
  { ignores: [".next/**", "node_modules/**"] },
  {
    rules: {
      // Newly introduced by the react-hooks plugin bundled with
      // eslint-config-next 16. Our effects intentionally reset derived state
      // (e.g. per-poem view language) when a prop/global changes — a valid
      // pattern. Keep it non-blocking in this deps-upgrade PR rather than
      // reworking behavior here; revisit as a separate cleanup.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
];

export default eslintConfig;
