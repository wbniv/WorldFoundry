// config.rs — global configuration (replaces all C++ global variables)

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum TargetSystem {
    PlayStation = 0,
    Saturn      = 1,
    Windows     = 2,
    Dos         = 3,
    Linux       = 4,
}

impl TargetSystem {
    pub fn from_int(v: i32) -> Self {
        match v {
            0 => TargetSystem::PlayStation,
            1 => TargetSystem::Saturn,
            2 => TargetSystem::Windows,
            3 => TargetSystem::Dos,
            4 => TargetSystem::Linux,
            _ => TargetSystem::Windows,
        }
    }
}

pub struct Config {
    pub x_align:              i32,
    pub y_align:              i32,
    pub x_page:               i32,
    pub y_page:               i32,
    pub perm_x_page:          i32,
    pub perm_y_page:          i32,
    pub pal_x_page:           i32,
    pub pal_y_page:           i32,
    pub pal_x_align:          i32,
    pub pal_y_align:          i32,
    pub out_file:             String,  // output data file pattern
    pub out_dir:              String,
    pub ini_file:             String,
    pub texture_path:         String,
    pub vrml_path:            String,
    pub colour_cycle_file:    String,
    pub r_transparent:        i32,
    pub g_transparent:        i32,
    pub b_transparent:        i32,
    pub col_transparent:      u16,     // computed from r/g/b_transparent
    pub target:               TargetSystem,
    pub debug:                bool,
    pub verbose:              bool,
    pub frame:                bool,
    pub show_align:           bool,
    pub show_packing:         bool,
    pub crop_output:          bool,
    pub power_of2:            bool,
    pub align_to_size_multiple: bool,
    pub mip_mapping:          bool,
    pub source_control:       bool,
    pub force_translucent:    bool,
    pub flip_y_out:           bool,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            x_align:              16,
            y_align:              1,
            x_page:               512,
            y_page:               2048,
            perm_x_page:          128,
            perm_y_page:          512,
            pal_x_page:           320,
            pal_y_page:           8,
            pal_x_align:          16,
            pal_y_align:          1,
            out_file:             "room%d.bin".to_string(),
            out_dir:              ".".to_string(),
            ini_file:             String::new(),
            texture_path:         String::new(),
            vrml_path:            String::new(),
            colour_cycle_file:    String::new(),
            r_transparent:        0,
            g_transparent:        0,
            b_transparent:        0,
            col_transparent:      0,
            target:               TargetSystem::Windows,
            debug:                false,
            verbose:              false,
            frame:                false,
            show_align:           false,
            show_packing:         false,
            crop_output:          true,
            power_of2:            false,
            align_to_size_multiple: false,
            mip_mapping:          false,
            source_control:       false,
            force_translucent:    false,
            flip_y_out:           false,
        }
    }
}
