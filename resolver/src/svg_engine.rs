use usvg::{Options, Tree, TreeParsing};
use tiny_skia::{Pixmap, Transform};
use image::{RgbaImage, Rgba};

pub fn render_svg_to_image(svg_data: &[u8], max_w: u32) -> Option<RgbaImage> {
    let opt = Options::default();
    let tree = Tree::from_data(svg_data, &opt).ok()?;
    let size = tree.size;
    let w = size.width();
    let h = size.height();
    if w <= 0.0 || h <= 0.0 {
        return None;
    }
    let target_w = max_w.min(1200).max(100);
    let scale = (target_w as f32) / w;
    let target_h = (h * scale).max(1.0) as u32;
    let mut pixmap = Pixmap::new(target_w, target_h)?;
    resvg::render(&tree, Transform::from_scale(scale, scale), &mut pixmap.as_mut());
    
    let mut img = RgbaImage::new(target_w, target_h);
    let data = pixmap.data();
    for (i, pixel) in img.pixels_mut().enumerate() {
        let idx = i * 4;
        let r = data[idx];
        let g = data[idx + 1];
        let b = data[idx + 2];
        let a = data[idx + 3];
        if a > 0 && a < 255 {
            let r_un = ((r as u32 * 255) / a as u32).min(255) as u8;
            let g_un = ((g as u32 * 255) / a as u32).min(255) as u8;
            let b_un = ((b as u32 * 255) / a as u32).min(255) as u8;
            *pixel = Rgba([r_un, g_un, b_un, a]);
        } else {
            *pixel = Rgba([r, g, b, a]);
        }
    }
    Some(img)
}
