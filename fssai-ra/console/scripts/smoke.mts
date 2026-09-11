/**
 * Initial-render smoke check.
 *
 * `tsc --noEmit` proves the props line up. It does not prove the app renders.
 * This mounts the whole component tree once, with storage and network stubbed,
 * and fails if anything throws or if the landing content is missing. It runs in
 * CI alongside the Python suite, so a console that cannot start is caught in the
 * same place as a control plane that cannot start.
 */
import React from "react";
import { renderToString } from "react-dom/server";

(globalThis as Record<string, unknown>).localStorage = {
  getItem: () => "dev-officer-token",
  setItem: () => undefined,
};
(globalThis as Record<string, unknown>).fetch = async () => ({
  ok: true,
  status: 200,
  text: async () => "{}",
});

const { App } = await import("../src/App");
const html = renderToString(React.createElement(App));

const required = [
  "FSSAI",
  "Deployment",
  "Governance",
  "Actions",
  "Intelligence",
  "Evidence",
  "Assurance",
  "cannot manufacture the authority",
];
const missing = required.filter((marker) => !html.includes(marker));
if (missing.length > 0) {
  console.error(`console render is missing: ${missing.join(", ")}`);
  process.exit(1);
}
console.log(`console rendered ${html.length} bytes; all ${required.length} markers present`);
