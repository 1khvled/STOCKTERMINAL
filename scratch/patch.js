const fs = require('fs');

let js = fs.readFileSync('app/static/js/dashboard.js', 'utf8');

// Replace standard document.getElementById assignments safely
js = js.replace(/document\.getElementById\(['"]([^'"]+)['"]\)\.innerText\s*=/g, "const el_$1 = document.getElementById('$1'); if(el_$1) el_$1.innerText =");
js = js.replace(/document\.getElementById\(['"]([^'"]+)['"]\)\.innerHTML\s*=/g, "const el_$1 = document.getElementById('$1'); if(el_$1) el_$1.innerHTML =");

fs.writeFileSync('app/static/js/dashboard.js', js, 'utf8');
console.log("Patched dashboard.js!");
