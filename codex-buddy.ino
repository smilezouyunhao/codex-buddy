/*
 * Codex Buddy — M5Stick S3 ASCII 兔兔
 * 6 状态按键切换，动态居中，仅面部
 */

#include <M5Unified.h>

enum PetState { SLEEP, IDLE, WORKING, ATTENTION, DONE, ERROR_ST, STATE_COUNT };
const char* state_names[] = {"Sleep","Idle","Working","Attention","Done","Error"};

PetState g_state  = SLEEP;
bool     g_redraw = true;

const char* pet_sleep[]     = { " (\\_/) ", " (-_-) ", " z z z  " };
const char* pet_idle[]      = { " (\\_/) ", " (o_o) ", "  / >   " };
const char* pet_working[]   = { " (\\_/) ", " (>_<) ", " ~ ~ ~  " };
const char* pet_attention[] = { " (\\_/) ", " (O_O) ", " ! ! !  " };
const char* pet_done[]      = { " (\\_/) ", " (^_^) ", " / >*   " };
const char* pet_error[]     = { " (\\_/) ", " (x_x) ", " / >X   " };

const char** pet_frames[] = {
  pet_sleep, pet_idle, pet_working, pet_attention, pet_done, pet_error,
};

static void draw_rabbit(PetState s) {
  M5GFX &g = M5.Lcd;
  g.startWrite();
  g.fillScreen(TFT_BLACK);

  // 标题
  g.setTextSize(1);
  g.setTextColor(TFT_LIGHTGREY);
  g.drawCenterString(state_names[s], g.width() / 2, 4);

  // ASCII 宠物 — setTextSize(2) 放大，固定等宽 X，3 行对齐
  uint16_t c = (s == ATTENTION) ? 0xFBE0 : (s == ERROR_ST) ? 0xF800 : TFT_WHITE;
  g.setTextColor(c);
  g.setTextSize(2);
  const char** lines = pet_frames[s];
  int w = g.textWidth(pet_idle[0]);
  int x = (g.width() - w) / 2;
  int first_y = g.height() / 2 - 24;
  for (int i = 0; i < 3; i++) {
    g.setCursor(x, first_y + i * 20);
    g.print(lines[i]);
  }

  // 按键 — 动态右对齐
  g.setTextSize(1);
  g.setTextColor(TFT_DARKGREY);
  g.setCursor(2, g.height() - 14);  g.print("[A]next");
  const char* r = "[B]prev";
  g.setCursor(g.width() - g.textWidth(r) - 4, g.height() - 14);
  g.print(r);

  g.endWrite();
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  M5.Lcd.setRotation(1);
  M5.Lcd.fillScreen(TFT_BLACK);
  draw_rabbit(SLEEP);
}

void loop() {
  M5.update();
  if (M5.BtnA.wasPressed()) { g_state = (PetState)((g_state + 1) % STATE_COUNT); g_redraw = true; }
  if (M5.BtnB.wasPressed()) { g_state = (PetState)((g_state + STATE_COUNT - 1) % STATE_COUNT); g_redraw = true; }
  if (g_redraw) { g_redraw = false; draw_rabbit(g_state); }
  delay(50);
}
