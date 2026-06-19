const fs = require('fs');
const js = fs.readFileSync('app/static/js/dashboard.js', 'utf8');
const html = fs.readFileSync('app/templates/dashboard.html', 'utf8');

const regex = /document\.getElementById\(['"]([^'"]+)['"]\)/g;
let match;
let missing = new Set();

while ((match = regex.exec(js)) !== null) {
  const id = match[1];
  if (!html.includes('id="' + id + '"') && !html.includes("id='" + id + "'")) {
    missing.add(id);
  }
}

console.log("Missing elements:", Array.from(missing));
