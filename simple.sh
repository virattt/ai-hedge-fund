#!/bin/bash

# List of cryptocurrencies (shortened as per your request)
TOP_20_CRYPTO=("BTC" "ETH" "BNB" "DOGE" "SOL")

# Output directory for individual analysis results
OUTPUT_DIR="./crypto_analysis_results"
mkdir -p "$OUTPUT_DIR"

# Date range for analysis
START_DATE="2025-01-01"
END_DATE="2025-01-08"

# Simulate the space and enter keys for the poetry command
run_analysis() {
    local ticker="$1"
    local output_file="$2"

    # Display the poetry output on the screen and save it to a file
    echo " " | poetry run python src/main.py --ticker "$ticker" --start-date "$START_DATE" --end-date "$END_DATE" | tee "$output_file"
}

# Run analysis for each cryptocurrency
echo "Running analysis for cryptocurrencies..."
for TICKER in "${TOP_20_CRYPTO[@]}"; do
    echo "Analyzing $TICKER..."
    OUTPUT_FILE="${OUTPUT_DIR}/${TICKER}_analysis.txt"
    run_analysis "$TICKER" "$OUTPUT_FILE"
done

echo "Analysis completed for all cryptocurrencies. Aggregating summaries..."

# Aggregation file for final output
AGGREGATED_SUMMARY_FILE="./aggregated_summary.txt"
echo "Generating aggregated summary using Ollama..."

# Combine all results into one file
COMBINED_ANALYSIS_FILE="./combined_analysis.txt"
rm -f "$COMBINED_ANALYSIS_FILE"
for FILE in "$OUTPUT_DIR"/*.txt; do
    echo "File: $FILE" >> "$COMBINED_ANALYSIS_FILE"
    cat "$FILE" >> "$COMBINED_ANALYSIS_FILE"
    echo -e "\n\n" >> "$COMBINED_ANALYSIS_FILE"
done

# Use Ollama for summarization
SUMMARY_PROMPT="You will suggest a cryptocurrency portfolio given the signals you receive in this prompt."

# Create a temporary input file that combines the SUMMARY_PROMPT and COMBINED_ANALYSIS_FILE
TEMP_INPUT_FILE="./temp_input.txt"
echo "$SUMMARY_PROMPT" > "$TEMP_INPUT_FILE"
cat "$COMBINED_ANALYSIS_FILE" >> "$TEMP_INPUT_FILE"

# Run Ollama with the combined input
ollama run llama3:latest < "$TEMP_INPUT_FILE" > "$AGGREGATED_SUMMARY_FILE"

# Clean up temporary file
rm -f "$TEMP_INPUT_FILE"

echo "Aggregation complete. See the results in $AGGREGATED_SUMMARY_FILE."

cat "$AGGREGATED_SUMMARY_FILE"

