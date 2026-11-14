use image::{imageops, Rgba, RgbaImage};
use std::path::Path;

#[derive(Debug, Clone, Copy)]
pub struct Rect {
    pub min_x: u32,
    pub min_y: u32,
    pub width: u32,
    pub height: u32,
}

pub fn detect_solid_background(im: &RgbaImage, tolerance: u32) -> (bool, Rgba<u8>, Option<Rect>) {
    let (w, h) = im.dimensions();
    if w < 10 || h < 10 {
        return (false, Rgba([255, 255, 255, 255]), None);
    }

    let mut perimeter = Vec::new();
    let step_x = (w / 40).max(1);
    let step_y = (h / 20).max(1);

    for x in (0..w).step_by(step_x as usize) {
        perimeter.push(*im.get_pixel(x, 0));
        perimeter.push(*im.get_pixel(x, h - 1));
    }
    for y in (1..h - 1).step_by(step_y as usize) {
        perimeter.push(*im.get_pixel(0, y));
        perimeter.push(*im.get_pixel(w - 1, y));
    }

    let trans_count = perimeter.iter().filter(|p| p[3] < 30).count();
    if trans_count > perimeter.len() * 4 / 10 {
        // Transparent background
        let mut min_x = w;
        let mut max_x = 0;
        let mut min_y = h;
        let mut max_y = 0;
        let mut found = false;
        for y in 0..h {
            for x in 0..w {
                if im.get_pixel(x, y)[3] > 30 {
                    found = true;
                    if x < min_x { min_x = x; }
                    if x > max_x { max_x = x; }
                    if y < min_y { min_y = y; }
                    if y > max_y { max_y = y; }
                }
            }
        }
        if !found {
            return (true, Rgba([0, 0, 0, 0]), None);
        }
        let rect = Rect {
            min_x,
            min_y,
            width: max_x - min_x + 1,
            height: max_y - min_y + 1,
        };
        return (true, Rgba([0, 0, 0, 0]), Some(rect));
    }

    let r_avg: u32 = perimeter.iter().map(|p| p[0] as u32).sum::<u32>() / perimeter.len() as u32;
    let g_avg: u32 = perimeter.iter().map(|p| p[1] as u32).sum::<u32>() / perimeter.len() as u32;
    let b_avg: u32 = perimeter.iter().map(|p| p[2] as u32).sum::<u32>() / perimeter.len() as u32;
    let bg_ref = Rgba([r_avg as u8, g_avg as u8, b_avg as u8, 255]);

    let matching = perimeter.iter().filter(|p| {
        (p[0] as i32 - r_avg as i32).abs() as u32 <= tolerance
            && (p[1] as i32 - g_avg as i32).abs() as u32 <= tolerance
            && (p[2] as i32 - b_avg as i32).abs() as u32 <= tolerance
    }).count();

    let diff_thresh = (tolerance * 3 / 2).max(35);
    let mut min_x = w;
    let mut max_x = 0;
    let mut min_y = h;
    let mut max_y = 0;
    let mut found = false;

    if matching < perimeter.len() * 8 / 10 {
        // Not a uniform border, find any non-white/non-transparent pixel
        for y in 0..h {
            for x in 0..w {
                let p = im.get_pixel(x, y);
                if p[3] > 30 && (p[0] < 245 || p[1] < 245 || p[2] < 245) {
                    found = true;
                    if x < min_x { min_x = x; }
                    if x > max_x { max_x = x; }
                    if y < min_y { min_y = y; }
                    if y > max_y { max_y = y; }
                }
            }
        }
        let rect = if found {
            Some(Rect {
                min_x,
                min_y,
                width: max_x - min_x + 1,
                height: max_y - min_y + 1,
            })
        } else {
            None
        };
        return (false, Rgba([255, 255, 255, 255]), rect);
    }

    // Uniform border found! Find content bounding box
    for y in 0..h {
        for x in 0..w {
            let p = im.get_pixel(x, y);
            let diff = (p[0] as i32 - r_avg as i32).abs() as u32
                + (p[1] as i32 - g_avg as i32).abs() as u32
                + (p[2] as i32 - b_avg as i32).abs() as u32;
            if diff > diff_thresh {
                found = true;
                if x < min_x { min_x = x; }
                if x > max_x { max_x = x; }
                if y < min_y { min_y = y; }
                if y > max_y { max_y = y; }
            }
        }
    }

    if !found {
        return (true, bg_ref, None);
    }

    let rect = Rect {
        min_x,
        min_y,
        width: max_x - min_x + 1,
        height: max_y - min_y + 1,
    };
    (true, bg_ref, Some(rect))
}

pub fn is_high_quality_brand(im: &RgbaImage) -> bool {
    let (w, h) = im.dimensions();
    if w < 60 && h < 30 {
        return false;
    }
    let (_, _, bbox) = detect_solid_background(im, 25);
    let rect = match bbox {
        Some(r) => r,
        None => return false,
    };
    if rect.width < 45 || rect.height < 18 {
        return false;
    }
    true
}

pub fn render_banner(im: &RgbaImage, target_path: &Path) -> Result<bool, Box<dyn std::error::Error + Send + Sync>> {
    if !is_high_quality_brand(im) {
        return Ok(false);
    }

    let (is_solid, bg_color, bbox) = detect_solid_background(im, 25);
    let rect = match bbox {
        Some(r) => r,
        None => return Ok(false),
    };

    let mut content = imageops::crop_imm(im, rect.min_x, rect.min_y, rect.width, rect.height).to_image();
    let mut cw = content.width();
    let mut ch = content.height();
    if cw < 20 || ch < 10 {
        return Ok(false);
    }

    let target_w = 320u32;
    let target_h = 70u32;
    let max_content_w = 288u32;
    let max_content_h = 54u32;

    // Smart horizontal splitter for stacked logos (aspect < 1.35 and tall enough)
    let aspect = cw as f32 / ch as f32;
    if aspect < 1.35 && ch >= 80 {
        let mid_start = (ch as f32 * 0.30) as u32;
        let mid_end = (ch as f32 * 0.70) as u32;
        let mut best_gap_y = None;
        let mut min_row_density = u32::MAX;

        for y in mid_start..mid_end {
            let mut diffs = 0;
            for x in 0..cw {
                let p = content.get_pixel(x, y);
                if is_solid && bg_color[3] > 0 {
                    let d = (p[0] as i32 - bg_color[0] as i32).abs() as u32
                        + (p[1] as i32 - bg_color[1] as i32).abs() as u32
                        + (p[2] as i32 - bg_color[2] as i32).abs() as u32;
                    if d > 35 { diffs += 1; }
                } else if p[3] > 30 {
                    diffs += 1;
                }
            }
            if diffs < min_row_density {
                min_row_density = diffs;
                best_gap_y = Some(y);
            }
        }

        if let Some(gap_y) = best_gap_y {
            if min_row_density <= 3.max(cw / 20) {
                let top_part = imageops::crop_imm(&content, 0, 0, cw, gap_y).to_image();
                let bot_part = imageops::crop_imm(&content, 0, gap_y, cw, ch - gap_y).to_image();
                let (_, _, top_bbox) = detect_solid_background(&top_part, 25);
                let (_, _, bot_bbox) = detect_solid_background(&bot_part, 25);

                if let (Some(tb), Some(bb)) = (top_bbox, bot_bbox) {
                    let top_c = imageops::crop_imm(&top_part, tb.min_x, tb.min_y, tb.width, tb.height).to_image();
                    let bot_c = imageops::crop_imm(&bot_part, bb.min_x, bb.min_y, bb.width, bb.height).to_image();

                    let h_target = 50f32;
                    let scale_top = h_target / top_c.height() as f32;
                    let scale_bot = h_target / bot_c.height() as f32;
                    let top_w = (top_c.width() as f32 * scale_top).max(1.0) as u32;
                    let bot_w = (bot_c.width() as f32 * scale_bot).max(1.0) as u32;
                    let gap = 14u32;
                    let total_w = top_w + gap + bot_w;

                    if total_w <= max_content_w && total_w >= 110 {
                        let top_resized = imageops::resize(&top_c, top_w, h_target as u32, imageops::FilterType::Lanczos3);
                        let bot_resized = imageops::resize(&bot_c, bot_w, h_target as u32, imageops::FilterType::Lanczos3);

                        let mut rearranged = RgbaImage::from_pixel(total_w, h_target as u32, bg_color);
                        imageops::overlay(&mut rearranged, &top_resized, 0, 0);
                        imageops::overlay(&mut rearranged, &bot_resized, (top_w + gap) as i64, 0);

                        content = rearranged;
                        cw = total_w;
                        ch = h_target as u32;
                    }
                }
            }
        }
    }

    // Scale to fit max_content_w x max_content_h
    let scale = (max_content_w as f32 / cw as f32).min(max_content_h as f32 / ch as f32);
    let new_w = (cw as f32 * scale).max(1.0) as u32;
    let new_h = (ch as f32 * scale).max(1.0) as u32;

    // Allow compact crests / military badges (reject only if < 40px wide or < 20px tall)
    if new_w < 40 || new_h < 20 {
        return Ok(false);
    }

    // Determine canvas background
    let canvas_bg = if is_solid && bg_color[3] > 0 && (bg_color[0] < 240 || bg_color[1] < 240 || bg_color[2] < 240) {
        bg_color
    } else {
        // Transparent or white background: check if content is all white
        let visible_pixels: Vec<&Rgba<u8>> = content.pixels().filter(|p| p[3] > 64).collect();
        let mean_luma = if !visible_pixels.is_empty() {
            let sum: f32 = visible_pixels.iter().map(|p| 0.299 * p[0] as f32 + 0.587 * p[1] as f32 + 0.114 * p[2] as f32).sum();
            sum / visible_pixels.len() as f32
        } else {
            0.0
        };
        if mean_luma > 225.0 {
            Rgba([24, 32, 44, 255]) // dark navy for all-white artwork
        } else {
            Rgba([255, 255, 255, 255])
        }
    };

    let mut canvas = RgbaImage::from_pixel(target_w, target_h, canvas_bg);
    let resized = imageops::resize(&content, new_w, new_h, imageops::FilterType::Lanczos3);

    let paste_x = ((target_w - new_w) / 2) as i64;
    let paste_y = ((target_h - new_h) / 2) as i64;
    imageops::overlay(&mut canvas, &resized, paste_x, paste_y);

    canvas.save(target_path)?;

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(target_path, std::fs::Permissions::from_mode(0o777));
    }

    Ok(true)
}
