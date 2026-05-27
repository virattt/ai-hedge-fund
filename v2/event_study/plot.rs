use super::models::EventStudyResult;
use anyhow::{Context, Result};
use std::fs::File;
use std::io::Write;

pub fn save_car_results_csv(result: &EventStudyResult, file_path: &str) -> Result<()> {
    let mut file = File::create(file_path).context("Failed to create CSV output file")?;

    writeln!(
        file,
        "ticker,event_date,source_type,report_period,eps_surprise,beta,r_squared,car_0_1,car_0_5,car_0_20"
    )?;

    for e in &result.events {
        let eps = e.eps_surprise.as_deref().unwrap_or("-");
        let car_0_1 = e
            .car_0_1
            .map(|v| v.to_string())
            .unwrap_or_else(|| "".to_string());
        let car_0_5 = e
            .car_0_5
            .map(|v| v.to_string())
            .unwrap_or_else(|| "".to_string());
        let car_0_20 = e
            .car_0_20
            .map(|v| v.to_string())
            .unwrap_or_else(|| "".to_string());

        writeln!(
            file,
            "{},{},{},{},{},{:.4},{:.4},{},{},{}",
            e.ticker,
            e.event_date,
            e.source_type,
            e.report_period,
            eps,
            e.market_model.beta,
            e.market_model.r_squared,
            car_0_1,
            car_0_5,
            car_0_20
        )?;
    }

    Ok(())
}
