/**
 * esbuild bundler config.
 *
 * Empaqueta JS en un solo archivo minificado con tree-shaking.
 * Soporta GSAP, Alpine.js y Lenis como dependencias bundleadas.
 */
import esbuild from "esbuild";

const isProduction = process.argv.includes("--production");
const isWatch = process.argv.includes("--watch");

/** @type {import('esbuild').BuildOptions} */
const sharedConfig = {
  bundle: true,
  minify: isProduction,
  sourcemap: !isProduction,
  target: ["es2020"],
  format: "iife",
  platform: "browser",
  logLevel: "info",
};

const configs = [
  {
    ...sharedConfig,
    entryPoints: ["static/src/js/main.js"],
    outfile: "static/dist/js/main.js",
  },
  {
    ...sharedConfig,
    entryPoints: ["static/src/js/encuesta.js"],
    outfile: "static/dist/js/encuesta.js",
  },
];

if (isWatch) {
  const ctxs = await Promise.all(configs.map(c => esbuild.context(c)));
  await Promise.all(ctxs.map(c => c.watch()));
  console.log("👀 esbuild watching for changes...");
} else {
  await Promise.all(configs.map(c => esbuild.build(c)));
  console.log(`✅ esbuild build complete${isProduction ? " (production)" : ""}`);
}
