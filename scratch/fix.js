const fs = require('fs');

let js = fs.readFileSync('app/static/js/dashboard.js', 'utf8');

// The dashboard.js is currently broken due to my previous script. Let's revert it or fix it.
// Oh wait, I don't have the original dashboard.js. I need to fix the invalid variable names.
// Let's use regex to find all "const el_something-something =" and replace the hyphens in the variable name.

js = js.replace(/const el_([a-zA-Z0-9\-]+) = document\.getElementById\('([^']+)'\); if\(el_\1\) el_\1\.(innerText|innerHTML) =/g, (match, varName, id, prop) => {
    const safeVarName = varName.replace(/-/g, '_');
    return `const el_${safeVarName} = document.getElementById('${id}'); if(el_${safeVarName}) el_${safeVarName}.${prop} =`;
});

fs.writeFileSync('app/static/js/dashboard.js', js, 'utf8');
console.log("Fixed dashboard.js syntax errors!");
