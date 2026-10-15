--[[
  Sends the lidar scan to the ground through the OSD.

  Reads an LD06/LD19/D500 on a serial port set to Scripting, bins each turn
  into 144 sectors of 2.5 degrees and writes it, three frames per turn, as
  characters on the bottom OSD rows. The VTX carries the characters with the
  video; the ground reads them back (lidar/osd/osdscan.py). Format in
  lidar/osd/README.md - keep it and osdscan.py in step with this file.

  Each turn also goes to a Scripting proximity backend if there is one
  (PRX1_TYPE 15), so the vehicle avoids obstacles from the same data.

  Parameters: SERIALn_PROTOCOL 28, SERIALn_BAUD 230 for the lidar,
  OSD_TYPE 5 with an MSP DisplayPort serial port, SCR_ENABLE 1.
  Needs osd:write, which is in ArduPilot master, not in 4.7.1.
--]]

local M = {}

M.BINS = 144
M.BIN_DEG = 360 / M.BINS
M.PARTS = 3
M.PER_PART = M.BINS // M.PARTS
M.DMIN = 50        -- mm, code 1
M.DMAX = 12000     -- mm, code 511
M.CODE_MAX = 511
M.LOG_STEP = math.log(M.DMAX / M.DMIN) / (M.CODE_MAX - 1)
-- 64 symbols, 6 bits each. Must be 64 distinct glyphs in the VTX font:
-- the Walksnail font draws s-y like b, d, f, h, j, l, n (the same arrows),
-- so those are < > [ ] % @ /. Keep in step with osdscan.py.
M.ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqr<>[]%@/z-+"
-- id, part, payload, attitude, crc = 81. Before 15. 10. 2026 there was no
-- attitude and a frame was 77; the ground reads both.
M.ATT_CHARS = 4    -- yaw 12 bits (360/4096 deg), roll 6, pitch 6 (1.5 deg, -48..46.5)
M.FRAME_CHARS = 2 + M.PER_PART * 9 // 6 + M.ATT_CHARS + 3
M.COLS = 50        -- HD canvas, OSD1_TXT_RES 1
M.ROWS = 18
M.WRITE_MAX = 25   -- MSP DisplayPort takes at most 30 characters a write

local SYM = {}
for i = 1, #M.ALPHABET do SYM[i - 1] = M.ALPHABET:sub(i, i) end

-- distance in mm to a 9-bit code: 0 no return, else logarithmic,
-- about 1.1 per cent a step (1 cm at 1 m, 9 cm at 8 m)
function M.code(d)
  if d <= 0 then return 0 end
  if d <= M.DMIN then return 1 end
  local v = math.floor(math.log(d / M.DMIN) / M.LOG_STEP + 1.5)
  if v > M.CODE_MAX then v = M.CODE_MAX end
  return v
end

-- CRC-16/CCITT-FALSE over the symbol values
-- tables written out: building them costs more than SCR_VM_I_COUNT allows
local CRC16 = { [0] =
  0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7, 0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
  0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6, 0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
  0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485, 0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
  0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4, 0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
  0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823, 0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
  0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12, 0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
  0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41, 0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
  0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70, 0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
  0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F, 0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
  0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E, 0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
  0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D, 0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
  0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C, 0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
  0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB, 0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
  0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A, 0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
  0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9, 0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
  0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8, 0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0,
}

function M.crc16(syms)
  local c = 0xFFFF
  for i = 1, #syms do
    c = ((c << 8) & 0xFFFF) ~ CRC16[(c >> 8) ~ syms[i]]
  end
  return c
end

-- attitude in radians (ArduPilot: yaw clockwise from north) -> the 4 symbols
function M.attitude(yaw, roll, pitch)
  local y = math.floor(math.deg(yaw) % 360 / 360 * 4096 + 0.5) % 4096
  local function tilt(a)
    local v = math.floor(math.deg(a) / 1.5 + 0.5) + 32
    if v < 0 then v = 0 elseif v > 63 then v = 63 end
    return v
  end
  return { y >> 6, y & 63, tilt(roll), tilt(pitch) }
end

-- frame `part` of a turn: dist[1..BINS] in mm (nil = no return) and its
-- attitude symbols (nil = level, north) -> string of FRAME_CHARS. Coded
-- here, a part at a time, to stay inside SCR_VM_I_COUNT.
function M.frame(scan_id, part, dist, att)
  local syms = { scan_id & 63, part }
  local acc, n = 0, 0
  local first = part * M.PER_PART
  for i = first + 1, first + M.PER_PART do
    acc = (acc << 9) | M.code(dist[i] or 0)
    n = n + 9
    while n >= 6 do
      n = n - 6
      syms[#syms + 1] = (acc >> n) & 63
    end
    acc = acc & ((1 << n) - 1)
  end
  att = att or { 0, 0, 32, 32 }
  for i = 1, M.ATT_CHARS do syms[#syms + 1] = att[i] end
  local c = M.crc16(syms)
  syms[#syms + 1] = (c >> 12) & 15
  syms[#syms + 1] = (c >> 6) & 63
  syms[#syms + 1] = c & 63
  local out = {}
  for i = 1, #syms do out[i] = SYM[syms[i]] end
  return table.concat(out)
end

-- LD06 packet: 0x54, 0x20|12 (the simulator sends 0x0C), speed, start angle,
-- 12 x (distance mm, intensity), end angle, timestamp, CRC-8 poly 0x4D
M.PACKET_LEN = 47
local CRC8 = { [0] =
  0x00, 0x4D, 0x9A, 0xD7, 0x79, 0x34, 0xE3, 0xAE, 0xF2, 0xBF, 0x68, 0x25, 0x8B, 0xC6, 0x11, 0x5C,
  0xA9, 0xE4, 0x33, 0x7E, 0xD0, 0x9D, 0x4A, 0x07, 0x5B, 0x16, 0xC1, 0x8C, 0x22, 0x6F, 0xB8, 0xF5,
  0x1F, 0x52, 0x85, 0xC8, 0x66, 0x2B, 0xFC, 0xB1, 0xED, 0xA0, 0x77, 0x3A, 0x94, 0xD9, 0x0E, 0x43,
  0xB6, 0xFB, 0x2C, 0x61, 0xCF, 0x82, 0x55, 0x18, 0x44, 0x09, 0xDE, 0x93, 0x3D, 0x70, 0xA7, 0xEA,
  0x3E, 0x73, 0xA4, 0xE9, 0x47, 0x0A, 0xDD, 0x90, 0xCC, 0x81, 0x56, 0x1B, 0xB5, 0xF8, 0x2F, 0x62,
  0x97, 0xDA, 0x0D, 0x40, 0xEE, 0xA3, 0x74, 0x39, 0x65, 0x28, 0xFF, 0xB2, 0x1C, 0x51, 0x86, 0xCB,
  0x21, 0x6C, 0xBB, 0xF6, 0x58, 0x15, 0xC2, 0x8F, 0xD3, 0x9E, 0x49, 0x04, 0xAA, 0xE7, 0x30, 0x7D,
  0x88, 0xC5, 0x12, 0x5F, 0xF1, 0xBC, 0x6B, 0x26, 0x7A, 0x37, 0xE0, 0xAD, 0x03, 0x4E, 0x99, 0xD4,
  0x7C, 0x31, 0xE6, 0xAB, 0x05, 0x48, 0x9F, 0xD2, 0x8E, 0xC3, 0x14, 0x59, 0xF7, 0xBA, 0x6D, 0x20,
  0xD5, 0x98, 0x4F, 0x02, 0xAC, 0xE1, 0x36, 0x7B, 0x27, 0x6A, 0xBD, 0xF0, 0x5E, 0x13, 0xC4, 0x89,
  0x63, 0x2E, 0xF9, 0xB4, 0x1A, 0x57, 0x80, 0xCD, 0x91, 0xDC, 0x0B, 0x46, 0xE8, 0xA5, 0x72, 0x3F,
  0xCA, 0x87, 0x50, 0x1D, 0xB3, 0xFE, 0x29, 0x64, 0x38, 0x75, 0xA2, 0xEF, 0x41, 0x0C, 0xDB, 0x96,
  0x42, 0x0F, 0xD8, 0x95, 0x3B, 0x76, 0xA1, 0xEC, 0xB0, 0xFD, 0x2A, 0x67, 0xC9, 0x84, 0x53, 0x1E,
  0xEB, 0xA6, 0x71, 0x3C, 0x92, 0xDF, 0x08, 0x45, 0x19, 0x54, 0x83, 0xCE, 0x60, 0x2D, 0xFA, 0xB7,
  0x5D, 0x10, 0xC7, 0x8A, 0x24, 0x69, 0xBE, 0xF3, 0xAF, 0xE2, 0x35, 0x78, 0xD6, 0x9B, 0x4C, 0x01,
  0xF4, 0xB9, 0x6E, 0x23, 0x8D, 0xC0, 0x17, 0x5A, 0x06, 0x4B, 0x9C, 0xD1, 0x7F, 0x32, 0xE5, 0xA8,
}

function M.new_parser(on_turn)
  local buf = ""
  local bins = {}
  local last_angle = nil
  local function turn_done()
    on_turn(bins)
    bins = {}
  end
  local function packet(p)
    local b = { p:byte(1, M.PACKET_LEN) }
    local c = 0
    for i = 1, M.PACKET_LEN - 1 do c = CRC8[c ~ b[i]] end
    if c ~= b[M.PACKET_LEN] then return false end
    local start = (b[5] | b[6] << 8) / 100
    local step = (((b[43] | b[44] << 8) / 100 - start) % 360) / 11
    for i = 0, 11 do
      local a = (start + step * i) % 360
      local d = b[7 + 3 * i] | b[8 + 3 * i] << 8
      if last_angle and a < last_angle - 180 then turn_done() end
      last_angle = a
      if d > 0 then
        local k = math.floor(a / M.BIN_DEG) % M.BINS + 1
        local old = bins[k]
        if not old or d < old then bins[k] = d end
      end
    end
    return true
  end
  local bad = 0
  return function(data)
    buf = buf .. data
    while true do
      local i = buf:find("\x54", 1, true)
      if not i then buf = ""; break end
      if #buf - i + 1 < M.PACKET_LEN then buf = buf:sub(i); break end
      if buf:byte(i + 1) & 0x1F == 12 and packet(buf:sub(i, i + M.PACKET_LEN - 1)) then
        buf = buf:sub(i + M.PACKET_LEN)
      else
        bad = bad + 1
        buf = buf:sub(i + 1)
      end
    end
    return bad
  end
end

-- string positions on screen for one frame, bottom rows, left to right
function M.layout(text)
  local rows = (#text + M.COLS - 1) // M.COLS
  local out = {}
  local row0 = M.ROWS - rows
  local pos = 1
  for r = 0, rows - 1 do
    local line = text:sub(pos, pos + M.COLS - 1)
    pos = pos + M.COLS
    for c = 1, #line, M.WRITE_MAX do
      out[#out + 1] = { c - 1, row0 + r, line:sub(c, c + M.WRITE_MAX - 1) }
    end
  end
  return out
end

if SCAN_OSD_TEST then return M end

---------------------------------------------------------------- on the vehicle

local OSD_PERIOD_MS = 100   -- the OSD thread redraws at 10 Hz
local port = serial:find_serial(0)
if not port then
  gcs:send_text(3, "scan_osd: no serial port with SERIALn_PROTOCOL 28")
  return
end
port:begin(230400)
port:set_flow_control(0)
local prx = proximity:get_backend(0)
if prx and prx:type() ~= 15 then prx = nil end

local scan_id = 0
local turn = nil            -- the turn on screen, mm per bin
local turn_att = nil        -- its attitude when it was finished
local part = M.PARTS        -- its next part to show; PARTS = all shown
local latest = nil          -- newest whole turn, shown when `turn` is out
local latest_att = nil
local to_prx = nil          -- newest turn not yet given to the proximity backend
local turns, sent = 0, 0
local last_osd, last_report = 0, 0

local parse = M.new_parser(function(bins)
  turns = turns + 1
  latest = bins
  latest_att = M.attitude(ahrs:get_yaw_rad(), ahrs:get_roll_rad(), ahrs:get_pitch_rad())
  to_prx = prx and bins
end)

local function update()
  local n = port:available():toint()
  if n > 0 then
    if n > 256 then n = 256 end   -- 17.6 kB/s comes in, 25.6 kB/s goes out at 100 Hz
    parse(port:readstring(n))
  end
  -- one of proximity or OSD a call, to stay inside SCR_VM_I_COUNT
  if to_prx then
    for i = 1, M.BINS do
      local d = to_prx[i]
      if d then prx:handle_script_distance_msg(d / 1000, (i - 0.5) * M.BIN_DEG, 0, false) end
    end
    prx:update_virtual_boundary()
    to_prx = nil
    return update, 10
  end
  local now = millis():toint()
  if part >= M.PARTS and latest then
    scan_id = (scan_id + 1) & 63
    turn, turn_att, latest, part = latest, latest_att, nil, 0
  end
  if now - last_osd >= OSD_PERIOD_MS and part < M.PARTS then
    last_osd = now
    local text = M.frame(scan_id, part, turn, turn_att)
    part = part + 1
    osd:draw_screen()           -- the normal OSD, so the pilot keeps it
    for _, w in ipairs(M.layout(text)) do osd:write(w[1], w[2], w[3]) end
    osd:flush()
    sent = sent + 1
  end
  if now - last_report >= 10000 then
    last_report = now
    gcs:send_text(6, string.format("scan_osd: %d turns, %d frames", turns, sent))
  end
  return update, 10
end

gcs:send_text(6, "scan_osd: started")
return update, 100
