// Loads the dataset files that the GitHub Actions build writes into ./data/,
// exposes them as the globals app.js already expects, then starts the app.
// The page never needs editing when a new dataset arrives; only the JSON changes.
async function loadJson(path) {
  try {
    const response = await fetch(path, { cache: "no-cache" });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return await response.json();
  } catch (error) {
    console.warn(`ORBIO: could not load ${path}; continuing without it.`, error);
    return {};
  }
}

const [omics, metadata] = await Promise.all([
  loadJson("./data/omics.json"),
  loadJson("./data/run_metadata.json")
]);
window.ORBIO_REPOSITORY_OMICS = omics;
window.ORBIO_RUN_METADATA = metadata;

await import("./app.js");
