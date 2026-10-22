# Preview styling update - 2026-10-22

Target: the existing AquaPulse Vue preview at http://127.0.0.1:5174, served from this frontend directory. PoolGuard is a separate app; no PoolGuard source changes were retained for this styling task.

Changes: icon navigation with aria-current, raised selected tabs, two-row mobile navigation, refreshed brand/status header, softer card surfaces, readable playback controls, and responsive fixes for Monitoring, Water Check and Resident preview. Existing local edits and workflow logic were retained. No dependencies, API behavior, weights or inference code changed.

Verification: npm.cmd run build (including vue-tsc) passed; npm.cmd run test passed 2 tests. Vite reports its existing large-bundle warning. Headless Edge at 1440, 768 and 390 pixels exercised all four tabs and active states with no page overflow or runtime errors. Screenshots were visually inspected. No uploads, model execution, audio activation, deployment or tunnel was performed. Backend Python tests were not rerun for these frontend-only changes.

Files: src/App.vue (navigation markup/accessibility), src/theme.css (presentation). The live Vite preview updates through HMR; refresh the page if needed.
