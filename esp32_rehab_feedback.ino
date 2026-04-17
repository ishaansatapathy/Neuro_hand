/*
 * ==========================================================================
 *  ESP32 Rehab Feedback — Vibration Motor / LED Controller
 * ==========================================================================
 *
 *  Receives single-character commands via USB Serial (115200 baud):
 *    '0' → OFF         (motor/LED off)
 *    '1' → MODERATE    (motor at ~55% power via PWM)
 *    '2' → SEVERE      (motor at 100% power via PWM)
 *
 *  Uses ESP32 LEDC PWM for smooth intensity control.
 *  Pin 18 is the default output — change MOTOR_PIN as needed.
 *
 * ==========================================================================
 */

const int MOTOR_PIN     = 18;

// ESP32 LEDC PWM configuration
const int PWM_CHANNEL    = 0;
const int PWM_FREQ       = 5000;    // 5 kHz — inaudible for motors
const int PWM_RESOLUTION = 8;       // 8-bit → 0–255 duty cycle

// Intensity levels (0–255)
const int INTENSITY_OFF      = 0;
const int INTENSITY_MODERATE = 140;  // ~55% duty — gentle nudge
const int INTENSITY_SEVERE   = 255;  // 100% duty — strong alert

void setup() {
  // Configure PWM
  ledcSetup(PWM_CHANNEL, PWM_FREQ, PWM_RESOLUTION);
  ledcAttachPin(MOTOR_PIN, PWM_CHANNEL);
  ledcWrite(PWM_CHANNEL, INTENSITY_OFF);

  Serial.begin(115200);
  Serial.println("ESP32 Rehab Feedback ready.");
}

void loop() {
  if (Serial.available()) {
    char val = Serial.read();

    if (val == '2') {
      ledcWrite(PWM_CHANNEL, INTENSITY_SEVERE);
    } else if (val == '1') {
      ledcWrite(PWM_CHANNEL, INTENSITY_MODERATE);
    } else if (val == '0') {
      ledcWrite(PWM_CHANNEL, INTENSITY_OFF);
    }
    // Ignore any other characters (newlines, etc.)
  }
}
