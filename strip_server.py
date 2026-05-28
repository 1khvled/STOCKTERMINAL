import re

file_path = r"C:\Users\Abdelli\Desktop\Projects\STOCK_TERMINAL_ALONE\app\server.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove auth import
content = re.sub(r'from auth import.*?\n', '', content)

# 2. Remove decorators
content = re.sub(r'@login_required\n', '', content)
content = re.sub(r'@premium_required\n', '', content)
content = re.sub(r'@admin_required\n', '', content)

# 3. Fix output directory reference
content = content.replace('Path("output")', r'Path("C:\\Users\\Abdelli\\Desktop\\Projects\\NEW PROJECT\\output")')
content = content.replace('"output"', r'"C:\\Users\\Abdelli\\Desktop\\Projects\\NEW PROJECT\\output"')

# 4. Remove all macro/cot/sentiment routes
# We'll truncate everything after @app.route("/cot")
idx = content.find('@app.route("/cot")')
if idx != -1:
    content_before = content[:idx]
    # We still need the run_server block at the end
    run_server_block = """
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

def run_server(port=5001):
    \"\"\"Start the local web server.\"\"\"
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info(f"\\n=======================================================")
    logger.info(f"   StockerAI Standalone Classic Terminal")
    logger.info(f"   Starting server on http://127.0.0.1:{port}")
    logger.info(f"=======================================================\\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

if __name__ == "__main__":
    run_server()
"""
    content = content_before + run_server_block

# 5. Reroute /stocks to /
content = content.replace('@app.route("/stocks")', '@app.route("/")')

# 6. Delete login/logout routes
content = re.sub(r'@app\.route\("/login".*?def login_page\(\):.*?(?=@app)', '', content, flags=re.DOTALL)
content = re.sub(r'@app\.route\("/logout"\).*?def logout\(\):.*?(?=@app)', '', content, flags=re.DOTALL)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Server stripped successfully.")
