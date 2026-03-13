FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Temporarily copy requirements to install python dependencies first
COPY requirements.txt .

# Install python packages (including playwright which provides the CLI)
RUN pip install --no-cache-dir -r requirements.txt

# Run Playwright's built-in dependency installer which knows exactly what apt packages it needs
# We also install some basic fonts for the PDF generation
RUN apt-get update && apt-get install -y fonts-liberation fonts-noto fonts-noto-cjk \
    && playwright install chromium \
    && playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Command to run the application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
