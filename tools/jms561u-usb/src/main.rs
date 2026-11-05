//! JMicron JMS561U flash access over USB through the vendor SCSI commands (Linux SG_IO, root).
//! Commands come from Ugreen's JMMassProd 1.16.15.7: flash read `DF 10`, READ BUFFER
//! descriptor `3C 03`, WRITE BUFFER `3B 0E` in 4 KiB chunks. The bridge accepts chunks only
//! in order from offset 0.
//!
//!   jms561u-usb info  <dev>
//!   jms561u-usb read  <dev> <offset> <len> <out>
//!   jms561u-usb write <dev> <image> <sha256> [--go]   (without --go: dry run, prints CDBs)
//!
//! WARNING. `write` sends a 128 KiB bank; the bridge stores it in copy 1 (flash 0x20000) and
//! leaves copy 0 alone. It cannot install the TRIM image (that lives in copy 0, see
//! docs/flashing.md), and if the image in copy 1 fails at run time only an SPI programmer
//! brings the enclosure back. This tool never erases: a chip erase over USB is what turned
//! our enclosure into a brick (docs/lessons.md).
use std::{env, fs, fs::File, os::fd::AsRawFd, process::exit};

mod sha256;

const SG_IO: u64 = 0x2285;
const FROM_DEV: i32 = -3;
const TO_DEV: i32 = -2;
const CHUNK: usize = 0x1000;
const BANK: usize = 0x20000;

#[repr(C)]
struct SgIoHdr {
    interface_id: i32, dxfer_direction: i32, cmd_len: u8, mx_sb_len: u8, iovec_count: u16,
    dxfer_len: u32, dxferp: *mut u8, cmdp: *const u8, sbp: *mut u8, timeout: u32, flags: u32,
    pack_id: i32, usr_ptr: *mut u8, status: u8, masked_status: u8, msg_status: u8, sb_len_wr: u8,
    host_status: u16, driver_status: u16, resid: i32, duration: u32, info: u32,
}

unsafe extern "C" {
    fn ioctl(fd: i32, req: u64, ...) -> i32;
}

fn sg(f: &File, cdb: &[u8], dir: i32, buf: &mut [u8], timeout_ms: u32) -> Result<(), String> {
    let mut sense = [0u8; 32];
    let mut h = SgIoHdr {
        interface_id: 'S' as i32, dxfer_direction: dir, cmd_len: cdb.len() as u8, mx_sb_len: 32,
        iovec_count: 0, dxfer_len: buf.len() as u32, dxferp: buf.as_mut_ptr(), cmdp: cdb.as_ptr(),
        sbp: sense.as_mut_ptr(), timeout: timeout_ms, flags: 0, pack_id: 0,
        usr_ptr: std::ptr::null_mut(), status: 0, masked_status: 0, msg_status: 0, sb_len_wr: 0,
        host_status: 0, driver_status: 0, resid: 0, duration: 0, info: 0,
    };
    if unsafe { ioctl(f.as_raw_fd(), SG_IO, &mut h as *mut SgIoHdr) } != 0 {
        return Err(format!("ioctl SG_IO: {}", std::io::Error::last_os_error()));
    }
    if h.status != 0 || h.host_status != 0 || h.driver_status != 0 || h.resid != 0 {
        return Err(format!("CDB {} failed: status {} host {} driver {} resid {} sense {}",
            hex(cdb), h.status, h.host_status, h.driver_status, h.resid, hex(&sense[..h.sb_len_wr as usize])));
    }
    Ok(())
}

fn hex(b: &[u8]) -> String { b.iter().map(|x| format!("{x:02x}")).collect::<Vec<_>>().join(" ") }

fn read_cdb(addr: usize, len: usize) -> [u8; 12] {
    [0xDF, 0x10, 0, (len >> 8) as u8, len as u8, 0, 0, 0, (addr >> 16) as u8, (addr >> 8) as u8, addr as u8, 0xFA]
}

fn write_cdb(off: usize) -> [u8; 10] {
    [0x3B, 0x0E, 0, (off >> 16) as u8, (off >> 8) as u8, off as u8, 0, (CHUNK >> 8) as u8, CHUNK as u8, 0]
}

fn chip_info(f: &File) -> Result<[u8; 16], String> {
    let mut b = [0u8; 16];
    sg(f, &[0xE0, 0xF4, 0xE7, 0, 0, 0, 0, 0, 0, 0, 0, 0], FROM_DEV, &mut b, 5000)?;
    Ok(b)
}

fn read(f: &File, addr: usize, len: usize) -> Result<Vec<u8>, String> {
    let mut out = Vec::with_capacity(len);
    for o in (addr..addr + len).step_by(CHUNK) {
        let n = CHUNK.min(addr + len - o);
        let mut b = vec![0u8; n];
        sg(f, &read_cdb(o, n), FROM_DEV, &mut b, 5000)?;
        out.extend_from_slice(&b);
    }
    Ok(out)
}

fn num(s: &str) -> usize {
    let r = s.strip_prefix("0x").map_or_else(|| s.parse(), |h| usize::from_str_radix(h, 16));
    r.unwrap_or_else(|_| die(&format!("bad number {s}")))
}

fn die(m: &str) -> ! { eprintln!("error: {m}"); exit(1) }

fn open_checked(dev: &str) -> File {
    let f = File::options().read(true).write(true).open(dev).unwrap_or_else(|e| die(&format!("{dev}: {e}")));
    let ci = chip_info(&f).unwrap_or_else(|e| die(&e));
    println!("chip info {}", hex(&ci));
    // JMS561U answers family 'e' and [6]=3 (normal firmware). Anything else: stop.
    if ci[5] != b'e' || ci[6] != 3 { die("not a JMS561U running its firmware (chip info [5]!='e' or [6]!=3)"); }
    f
}

fn main() {
    let a: Vec<String> = env::args().collect();
    match a.get(1).map(String::as_str) {
        Some("info") if a.len() == 3 => { open_checked(&a[2]); }
        Some("read") if a.len() == 6 => {
            let f = open_checked(&a[2]);
            let d = read(&f, num(&a[3]), num(&a[4])).unwrap_or_else(|e| die(&e));
            fs::write(&a[5], &d).unwrap_or_else(|e| die(&e.to_string()));
            println!("read {} bytes sha256 {}", d.len(), sha256::hex(&d));
        }
        Some("write") if a.len() == 5 || (a.len() == 6 && a[5] == "--go") => {
            let img = fs::read(&a[3]).unwrap_or_else(|e| die(&e.to_string()));
            let sum = sha256::hex(&img);
            if sum != a[4] { die(&format!("image sha256 {sum} != expected {}", a[4])); }
            if img.len() < BANK || &img[0x1fff0..0x1fff8] != b"EXROMEND" { die("image has no bank 1 with EXROMEND at 0x1fff0"); }
            let go = a.len() == 6;
            let f = if go { Some(open_checked(&a[2])) } else { None };
            if let Some(f) = &f {
                let mut d = [0u8; 4];
                sg(f, &[0x3C, 0x03, 0, 0, 0, 0, 0, 0, 4, 0], FROM_DEV, &mut d, 5000).unwrap_or_else(|e| die(&e));
                println!("buffer 0 descriptor {}", hex(&d));
                if d != [0x0c, 0x02, 0, 0] { die("buffer 0 descriptor is not 0c 02 00 00 (4 KiB, 128 KiB)"); }
            }
            for off in (0..BANK).step_by(CHUNK) {
                let cdb = write_cdb(off);
                match &f {
                    None => println!("dry {} data {}..{}", hex(&cdb), off, off + CHUNK),
                    Some(f) => {
                        let mut chunk = img[off..off + CHUNK].to_vec();
                        // First chunk erases the target bank, give it time.
                        sg(f, &cdb, TO_DEV, &mut chunk, 60_000).unwrap_or_else(|e| die(&format!("at 0x{off:05x}: {e}")));
                        println!("wrote 0x{off:05x}");
                    }
                }
            }
            match &f {
                None => println!("dry run only, add --go to write"),
                Some(f) => {
                    // The bridge picks the physical bank (0x4ff8 in fw 2018), so look for the image in both.
                    // 0x200..0x3ff is metadata the bridge rewrites; JMMassProd skips it too (sub_437660).
                    let flash = read(f, 0, 2 * BANK).unwrap_or_else(|e| die(&e));
                    let mut ok = None;
                    for b in 0..2 {
                        let bank = &flash[b * BANK..(b + 1) * BANK];
                        // The commit erases sector 0 and rewrites only 0x000..0x7ff: 0x800..0xfff reads FF.
                        let bad: Vec<usize> = (0..BANK).filter(|&i| !(0x200..0x400).contains(&i)
                            && !((0x800..0x1000).contains(&i) && bank[i] == 0xFF) && bank[i] != img[i]).collect();
                        println!("bank {b} (flash 0x{:05x}): {} bytes differ from image outside 0x200..0x3ff{}", b * BANK, bad.len(),
                            if bad.is_empty() { String::new() } else { format!(", first at 0x{:05x}", bad[0]) });
                        if bad.is_empty() { ok = Some(b); }
                    }
                    match ok {
                        Some(b) => println!("VERIFIED: image is in bank {b}. Power-cycle only now."),
                        None => die("image not found in flash: do NOT power-cycle, rewrite from offset 0"),
                    }
                }
            }
        }
        _ => die("usage: info <dev> | read <dev> <off> <len> <out> | write <dev> <image> <sha256> [--go]"),
    }
}

#[cfg(test)]
mod t {
    #[test]
    fn cdbs_match_jmmassprod() {
        assert_eq!(super::write_cdb(0x1f000), [0x3B, 0x0E, 0, 0x01, 0xF0, 0, 0, 0x10, 0, 0]);
        assert_eq!(super::read_cdb(0x46000, 0x1000), [0xDF, 0x10, 0, 0x10, 0, 0, 0, 0, 0x04, 0x60, 0, 0xFA]);
    }
}
