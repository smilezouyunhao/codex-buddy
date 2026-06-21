/*
 * Codex Buddy — M5Stick S3 像素兔兔
 * BLE 联动状态，RGB565 像素精灵
 */

#include <M5Unified.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <limits.h>
#include "background_bitmap.h"
#include "rabbit_bitmaps.h"

const char* BLE_DEVICE_NAME = "Codex Buddy";
const char* TOKEN_SERVICE_UUID = "7b4f6a10-6d5f-4a6e-9e6f-4f7b6f9a1001";
const char* TOKEN_CHAR_UUID    = "7b4f6a11-6d5f-4a6e-9e6f-4f7b6f9a1001";

enum PetState { SLEEP, IDLE, WORKING, ATTENTION, DONE, ERROR_ST, STATE_COUNT };
const char* state_names[] = {"SLEEP","IDLE","WORKING","ATTENTION","DONE","ERROR"};

PetState g_state  = SLEEP;
bool     g_redraw = true;

const int DEFAULT_TOKEN_TOTAL = 10000;
const unsigned long DONE_HOLD_MS = 5000;
const unsigned long BATTERY_REFRESH_MS = 30000;
int g_token_used = 0;
int g_token_total = DEFAULT_TOKEN_TOTAL;
bool g_ble_connected = false;
bool g_ble_was_connected = false;
unsigned long g_done_started_at = 0;
unsigned long g_reset_deadline_ms = 0;
long g_reset_display_minutes = -1;
bool g_reset_valid = false;
int g_battery_level = -1;
bool g_battery_charging = false;
unsigned long g_last_battery_check_ms = 0;

enum BuddyEventType { BLE_CONNECTED_EVENT, BLE_DISCONNECTED_EVENT, TOKEN_PAYLOAD_EVENT };

struct BuddyEvent {
  BuddyEventType type;
  int token_used;
  int token_total;
  bool reset_valid;
  long reset_seconds;
  bool has_state;
  PetState state;
};

QueueHandle_t g_buddy_event_queue = nullptr;

static void update_battery_status(bool force = false) {
  unsigned long now = millis();
  if (!force && now - g_last_battery_check_ms < BATTERY_REFRESH_MS) return;
  g_last_battery_check_ms = now;

  int level = M5.Power.getBatteryLevel();
  bool charging = M5.Power.isCharging() == m5::Power_Class::is_charging;
  if (level != g_battery_level || charging != g_battery_charging) {
    g_battery_level = level;
    g_battery_charging = charging;
    g_redraw = true;
  }
}

static bool parse_state_name(String state, PetState &parsed_state) {
  state.trim();
  state.toLowerCase();

  if (state == "sleep") parsed_state = SLEEP;
  else if (state == "idle") parsed_state = IDLE;
  else if (state == "working") parsed_state = WORKING;
  else if (state == "attention") parsed_state = ATTENTION;
  else if (state == "done") parsed_state = DONE;
  else if (state == "error") parsed_state = ERROR_ST;
  else return false;
  return true;
}

static bool parse_integer_field(String field, long &value) {
  field.trim();
  if (field.length() == 0) return false;

  int digit_start = 0;
  bool negative = field[0] == '-';
  if (negative || field[0] == '+') digit_start = 1;
  if (digit_start == field.length()) return false;

  unsigned long magnitude = 0;
  const unsigned long limit = negative ? (unsigned long)LONG_MAX + 1UL : (unsigned long)LONG_MAX;
  for (int i = digit_start; i < field.length(); ++i) {
    if (field[i] < '0' || field[i] > '9') return false;
    unsigned long digit = field[i] - '0';
    if (magnitude > (limit - digit) / 10UL) return false;
    magnitude = magnitude * 10UL + digit;
  }

  if (negative) {
    value = magnitude == (unsigned long)LONG_MAX + 1UL ? LONG_MIN : -(long)magnitude;
  } else {
    value = (long)magnitude;
  }
  return true;
}

static bool parse_token_payload(String payload, int &used, int &total, String &state, long &reset_seconds) {
  payload.trim();
  int comma = payload.indexOf(',');
  if (comma <= 0) return false;
  int second_comma = payload.indexOf(',', comma + 1);
  int third_comma = second_comma > 0 ? payload.indexOf(',', second_comma + 1) : -1;

  long parsed_used = 0;
  long parsed_total = 0;
  if (!parse_integer_field(payload.substring(0, comma), parsed_used)) return false;
  if (!parse_integer_field(
        payload.substring(comma + 1, second_comma > 0 ? second_comma : payload.length()),
        parsed_total
      )) return false;
  if (parsed_total <= 0 || parsed_total > INT_MAX) return false;

  if (parsed_used < 0) parsed_used = 0;
  if (parsed_used > parsed_total) parsed_used = parsed_total;

  used = (int)parsed_used;
  total = (int)parsed_total;
  state = second_comma > 0 ? payload.substring(second_comma + 1, third_comma > 0 ? third_comma : payload.length()) : "";
  if (third_comma > 0) {
    if (!parse_integer_field(payload.substring(third_comma + 1), reset_seconds)) return false;
    if (reset_seconds < -1 || reset_seconds > LONG_MAX / 1000L) return false;
  } else {
    reset_seconds = -1;
  }
  return true;
}

static void enqueue_buddy_event(const BuddyEvent &event) {
  if (g_buddy_event_queue != nullptr) {
    xQueueSend(g_buddy_event_queue, &event, portMAX_DELAY);
  }
}

static void apply_buddy_event(const BuddyEvent &event) {
  if (event.type == BLE_CONNECTED_EVENT) {
    g_ble_connected = true;
    g_ble_was_connected = true;
    g_state = IDLE;
  } else if (event.type == BLE_DISCONNECTED_EVENT) {
    g_ble_connected = false;
    g_state = g_ble_was_connected ? ERROR_ST : SLEEP;
  } else {
    g_token_used = event.token_used;
    g_token_total = event.token_total;
    g_reset_valid = event.reset_valid;
    g_reset_deadline_ms = millis() + (unsigned long)max(0L, event.reset_seconds) * 1000UL;
    g_reset_display_minutes = -1;
    if (event.has_state) {
      g_state = event.state;
      if (event.state == DONE) g_done_started_at = millis();
    }
  }
  g_redraw = true;
}

static void process_buddy_events() {
  BuddyEvent event;
  while (g_buddy_event_queue != nullptr && xQueueReceive(g_buddy_event_queue, &event, 0) == pdTRUE) {
    apply_buddy_event(event);
  }
}

class TokenCharacteristicCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *characteristic) override {
    int used = 0;
    int total = DEFAULT_TOKEN_TOTAL;
    String state = "";
    long reset_seconds = -1;
    if (parse_token_payload(characteristic->getValue(), used, total, state, reset_seconds)) {
      BuddyEvent event = {};
      event.type = TOKEN_PAYLOAD_EVENT;
      event.token_used = used;
      event.token_total = total;
      event.reset_valid = reset_seconds >= 0;
      event.reset_seconds = reset_seconds;
      event.has_state = parse_state_name(state, event.state);
      enqueue_buddy_event(event);
    }
  }
};

class BuddyServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *server) override {
    BuddyEvent event = {};
    event.type = BLE_CONNECTED_EVENT;
    enqueue_buddy_event(event);
  }

  void onDisconnect(BLEServer *server) override {
    BuddyEvent event = {};
    event.type = BLE_DISCONNECTED_EVENT;
    enqueue_buddy_event(event);
    server->startAdvertising();
  }
};

static void setup_ble() {
  BLEDevice::init(BLE_DEVICE_NAME);
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new BuddyServerCallbacks());

  BLEService *service = server->createService(TOKEN_SERVICE_UUID);
  BLECharacteristic *token_char = service->createCharacteristic(
    TOKEN_CHAR_UUID,
    BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_WRITE
  );

  token_char->setCallbacks(new TokenCharacteristicCallbacks());
  token_char->setValue("0,10000");
  service->start();

  BLEAdvertising *advertising = BLEDevice::getAdvertising();
  advertising->addServiceUUID(TOKEN_SERVICE_UUID);
  advertising->setScanResponse(true);
  server->startAdvertising();
}

static void draw_token_bar(int used, int total) {
  M5GFX &g = M5.Lcd;

  float ratio = total > 0 ? (float)used / total : 0.0f;
  if (ratio < 0.0f) ratio = 0.0f;
  if (ratio > 1.0f) ratio = 1.0f;

  uint16_t bar_color = TFT_GREEN;
  if (ratio >= 0.75f) bar_color = TFT_ORANGE;
  if (ratio >= 0.90f) bar_color = TFT_RED;

  int margin = 7;
  int bar_h = 14;
  int bar_w = g.width() - margin * 2;
  int bar_x = margin;
  int bar_y = 194;

  char label[32];
  int percent = (int)(ratio * 100.0f + 0.5f);
  snprintf(label, sizeof(label), "TOKEN %d%%", percent);

  g.setFont(&fonts::AsciiFont8x16);
  g.setTextSize(1);
  g.setTextColor(TFT_LIGHTGREY);
  g.drawCenterString(label, g.width() / 2, 167);

  g.drawRoundRect(bar_x, bar_y, bar_w, bar_h, 3, TFT_DARKGREY);
  int fill_w = (int)((bar_w - 4) * ratio);
  if (fill_w > 0) {
    g.fillRoundRect(bar_x + 2, bar_y + 2, fill_w, bar_h - 4, 2, bar_color);
  }

  char reset_label[24] = "RESET --";
  if (g_reset_valid) {
    long remaining_ms = (long)(g_reset_deadline_ms - millis());
    unsigned long remaining_minutes = remaining_ms > 0 ? ((unsigned long)remaining_ms + 59999UL) / 60000UL : 0;
    g_reset_display_minutes = remaining_minutes;
    if (remaining_minutes == 0) {
      snprintf(reset_label, sizeof(reset_label), "RESET NOW");
    } else {
      snprintf(reset_label, sizeof(reset_label), "RESET %luH%02luM", remaining_minutes / 60, remaining_minutes % 60);
    }
  }
  g.setTextColor(TFT_DARKGREY);
  g.drawCenterString(reset_label, g.width() / 2, 217);
}

static const char* battery_glyph(char c) {
  switch (c) {
    case '0': return "111101101101111";
    case '1': return "010110010010111";
    case '2': return "111001111100111";
    case '3': return "111001111001111";
    case '4': return "101101111001001";
    case '5': return "111100111001111";
    case '6': return "111100111101111";
    case '7': return "111001010010010";
    case '8': return "111101111101111";
    case '9': return "111101111001111";
    case '%': return "101001010100101";
    case '+': return "000010111010000";
    case '-': return "000000111000000";
    default:  return "000000000000000";
  }
}

static void draw_battery_pixel_text(int x, int y, const char* text, uint16_t color) {
  M5GFX &g = M5.Lcd;
  while (*text) {
    const char* glyph = battery_glyph(*text++);
    for (int row = 0; row < 5; ++row) {
      for (int col = 0; col < 3; ++col) {
        if (glyph[row * 3 + col] == '1') g.drawPixel(x + col, y + row, color);
      }
    }
    x += 4;
  }
}

static void draw_battery_status() {
  M5GFX &g = M5.Lcd;

  uint16_t color = TFT_DARKGREY;
  if (g_battery_level >= 0) {
    color = g_battery_level > 50 ? TFT_GREEN
          : g_battery_level > 20 ? TFT_ORANGE
          : TFT_RED;
  }
  if (g_battery_charging) color = TFT_YELLOW;

  char label[16];
  if (g_battery_level < 0) {
    snprintf(label, sizeof(label), "--");
  } else if (g_battery_charging) {
    snprintf(label, sizeof(label), "%d+", g_battery_level);
  } else {
    snprintf(label, sizeof(label), "%d%%", g_battery_level);
  }

  const int slot_x = 2;
  const int slot_w = 43;
  const int y = 5;
  const int body_w = 11;
  const int body_h = 7;
  const int label_w = strlen(label) * 4 - 1;
  const int content_w = body_w + 4 + label_w;
  const int x = slot_x + (slot_w - content_w) / 2;
  g.drawRect(x, y, body_w, body_h, color);
  g.fillRect(x + body_w, y + 2, 2, body_h - 4, color);

  if (g_battery_level >= 0) {
    int fill_w = (g_battery_level * (body_w - 4) + 99) / 100;
    if (fill_w > 0) g.fillRect(x + 2, y + 2, fill_w, body_h - 4, color);
  }

  draw_battery_pixel_text(x + body_w + 4, 6, label, color);
}

static void draw_rabbit(PetState s) {
  M5GFX &g = M5.Lcd;
  g.startWrite();
  bool previous_swap_bytes = g.getSwapBytes();
  g.setSwapBytes(true);
  g.pushImage(0, 0, BACKGROUND_WIDTH, BACKGROUND_HEIGHT, cyber_terminal_background);
  g.setSwapBytes(previous_swap_bytes);

  // 顶栏和像素风状态标题
  g.setFont(&fonts::Font0);
  g.setTextSize(1);
  draw_battery_status();
  g.setTextColor(g_ble_connected ? TFT_GREEN : TFT_DARKGREY);
  g.setFont(&fonts::AsciiFont8x16);
  g.setTextSize(0.75f);
  g.drawCenterString("BLE", 117, 3);
  g.setTextSize(1);
  g.setTextColor(TFT_LIGHTGREY);
  g.drawCenterString(state_names[s], g.width() / 2, 19);

  // 72x72 RGB565 像素精灵；洋红色作为透明色，不绘制底图方框。
  int rabbit_x = (g.width() - RABBIT_WIDTH) / 2;
  int content_top = 44;
  int content_bottom = 168;
  int rabbit_y = content_top + (content_bottom - content_top - RABBIT_HEIGHT) / 2;
  // 位图头文件使用原生 RGB565，而非预交换字节序。
  g.setSwapBytes(true);
  g.pushImage(
    rabbit_x,
    rabbit_y,
    RABBIT_WIDTH,
    RABBIT_HEIGHT,
    rabbit_bitmaps[s],
    RABBIT_TRANSPARENT
  );
  g.setSwapBytes(previous_swap_bytes);

  draw_token_bar(g_token_used, g_token_total);

  g.endWrite();
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  g_buddy_event_queue = xQueueCreate(16, sizeof(BuddyEvent));
  M5.Lcd.setRotation(0);
  M5.Lcd.fillScreen(TFT_BLACK);
  update_battery_status(true);
  setup_ble();
  draw_rabbit(SLEEP);
}

void loop() {
  M5.update();
  process_buddy_events();
  update_battery_status();

  if (g_ble_connected && g_state == DONE && millis() - g_done_started_at >= DONE_HOLD_MS) {
    g_state = IDLE;
    g_redraw = true;
  }

  if (g_reset_valid) {
    long remaining_ms = (long)(g_reset_deadline_ms - millis());
    long remaining_minutes = remaining_ms > 0 ? ((unsigned long)remaining_ms + 59999UL) / 60000UL : 0;
    if (remaining_minutes != g_reset_display_minutes) g_redraw = true;
  }

  if (g_redraw) { g_redraw = false; draw_rabbit(g_state); }
  delay(50);
}
