/*
 * Codex Buddy — M5Stick S3 ASCII 兔兔
 * BLE 联动状态，动态居中，仅面部
 */

#include <M5Unified.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>

const char* BLE_DEVICE_NAME = "Codex Buddy";
const char* TOKEN_SERVICE_UUID = "7b4f6a10-6d5f-4a6e-9e6f-4f7b6f9a1001";
const char* TOKEN_CHAR_UUID    = "7b4f6a11-6d5f-4a6e-9e6f-4f7b6f9a1001";

enum PetState { SLEEP, IDLE, WORKING, ATTENTION, DONE, ERROR_ST, STATE_COUNT };
const char* state_names[] = {"Sleep","Idle","Working","Attention","Done","Error"};

PetState g_state  = SLEEP;
bool     g_redraw = true;

const int DEFAULT_TOKEN_TOTAL = 10000;
const unsigned long DONE_HOLD_MS = 5000;
int g_token_used = 0;
int g_token_total = DEFAULT_TOKEN_TOTAL;
bool g_ble_connected = false;
bool g_ble_was_connected = false;
unsigned long g_done_started_at = 0;
char g_reset_label[20] = "Reset --:--";

const char* pet_sleep[]     = { " (\\_/) ", " (-.-) ", "  zZ   " };
const char* pet_idle[]      = { " (\\_/) ", " (o.o) ", "  > <  " };
const char* pet_working[]   = { " (\\_/) ", " (._.) ", " /|_|\\ " };
const char* pet_attention[] = { " (\\_/) ", " (O.O) ", "  !!!  " };
const char* pet_done[]      = { " (\\_/) ", " (^.^) ", "  /*   " };
const char* pet_error[]     = { " (\\_/) ", " (x.x) ", "  ???  " };

const char** pet_frames[] = {
  pet_sleep, pet_idle, pet_working, pet_attention, pet_done, pet_error,
};

static void set_state_from_ble(bool connected) {
  g_ble_connected = connected;
  if (connected) {
    g_ble_was_connected = true;
    g_state = IDLE;
  } else {
    g_state = g_ble_was_connected ? ERROR_ST : SLEEP;
  }
  g_redraw = true;
}

static void apply_state_name(String state) {
  state.trim();
  state.toLowerCase();

  if (state == "sleep") g_state = SLEEP;
  else if (state == "idle") g_state = IDLE;
  else if (state == "working") g_state = WORKING;
  else if (state == "attention") g_state = ATTENTION;
  else if (state == "done") {
    g_state = DONE;
    g_done_started_at = millis();
  }
  else if (state == "error") g_state = ERROR_ST;
}

static bool parse_token_payload(String payload, int &used, int &total, String &state, String &reset_label) {
  payload.trim();
  int comma = payload.indexOf(',');
  if (comma <= 0) return false;
  int second_comma = payload.indexOf(',', comma + 1);
  int third_comma = second_comma > 0 ? payload.indexOf(',', second_comma + 1) : -1;

  int parsed_used = payload.substring(0, comma).toInt();
  int parsed_total = payload.substring(comma + 1, second_comma > 0 ? second_comma : payload.length()).toInt();
  if (parsed_total <= 0) return false;

  if (parsed_used < 0) parsed_used = 0;
  if (parsed_used > parsed_total) parsed_used = parsed_total;

  used = parsed_used;
  total = parsed_total;
  state = second_comma > 0 ? payload.substring(second_comma + 1, third_comma > 0 ? third_comma : payload.length()) : "";
  reset_label = third_comma > 0 ? payload.substring(third_comma + 1) : "";
  return true;
}

class TokenCharacteristicCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *characteristic) override {
    int used = 0;
    int total = DEFAULT_TOKEN_TOTAL;
    String state = "";
    String reset_label = "";
    if (parse_token_payload(characteristic->getValue(), used, total, state, reset_label)) {
      g_token_used = used;
      g_token_total = total;
      if (reset_label.length() > 0) {
        reset_label.toCharArray(g_reset_label, sizeof(g_reset_label));
      }
      if (state.length() > 0) {
        apply_state_name(state);
      }
      g_redraw = true;
    }
  }
};

class BuddyServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *server) override {
    set_state_from_ble(true);
  }

  void onDisconnect(BLEServer *server) override {
    set_state_from_ble(false);
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

  int margin = 12;
  int bar_h = 10;
  int bar_w = g.width() - margin * 2;
  int bar_x = margin;
  int bar_y = g.height() - 28;

  char label[32];
  int percent = (int)(ratio * 100.0f + 0.5f);
  snprintf(label, sizeof(label), "Token %d%%", percent);

  g.setTextSize(1);
  g.setTextColor(TFT_LIGHTGREY);
  g.drawCenterString(label, g.width() / 2, bar_y - 13);

  g.drawRoundRect(bar_x, bar_y, bar_w, bar_h, 3, TFT_DARKGREY);
  int fill_w = (int)((bar_w - 4) * ratio);
  if (fill_w > 0) {
    g.fillRoundRect(bar_x + 2, bar_y + 2, fill_w, bar_h - 4, 2, bar_color);
  }

  g.setTextColor(TFT_DARKGREY);
  g.drawCenterString(g_reset_label, g.width() / 2, bar_y + 12);
}

static void draw_rabbit(PetState s) {
  M5GFX &g = M5.Lcd;
  g.startWrite();
  g.fillScreen(TFT_BLACK);

  // 标题
  g.setTextSize(1);
  g.setTextColor(TFT_LIGHTGREY);
  g.drawCenterString(state_names[s], g.width() / 2, 4);
  g.setTextColor(g_ble_connected ? TFT_GREEN : TFT_DARKGREY);
  g.drawRightString("BLE", g.width() - 4, 4);

  // ASCII 宠物 — setTextSize(2) 放大，固定等宽 X，3 行对齐
  uint16_t c = (s == ATTENTION) ? 0xFBE0 : (s == DONE) ? TFT_GREEN : (s == ERROR_ST) ? 0xF800 : TFT_WHITE;
  g.setTextColor(c);
  g.setTextSize(2);
  const char** lines = pet_frames[s];
  int w = g.textWidth(pet_idle[0]);
  int x = (g.width() - w) / 2;
  int first_y = g.height() / 2 - 28;
  for (int i = 0; i < 3; i++) {
    g.setCursor(x, first_y + i * 20);
    g.print(lines[i]);
  }

  draw_token_bar(g_token_used, g_token_total);

  g.endWrite();
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  M5.Lcd.setRotation(1);
  M5.Lcd.fillScreen(TFT_BLACK);
  setup_ble();
  draw_rabbit(SLEEP);
}

void loop() {
  M5.update();

  if (g_ble_connected && g_state == DONE && millis() - g_done_started_at >= DONE_HOLD_MS) {
    g_state = IDLE;
    g_redraw = true;
  }

  if (g_redraw) { g_redraw = false; draw_rabbit(g_state); }
  delay(50);
}
