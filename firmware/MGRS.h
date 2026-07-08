#pragma once
#include <math.h>
#include <stdio.h>
#include <string.h>

// WGS84 lat/lon (degrees) -> MGRS reference at 1 m precision,
// e.g. "19TCG0136228411" (15 chars + NUL). Self-contained, no deps.
//
// Uses the Kruger/Karney series for the UTM projection (sub-meter accurate),
// which is far better than needed for reading a 100 m grid square.
// Not handled: the Norway/Svalbard zone exceptions and polar (UPS) regions —
// irrelevant between 80S and 84N away from those special zones.
static bool mgrs_format(double lat, double lon, char* out, unsigned out_sz) {
  if (out_sz < 16 || lat < -80.0 || lat > 84.0 || lon < -180.0 || lon > 180.0)
    return false;

  int zone = (int)floor(lon / 6.0) + 31;
  if (zone > 60) zone = 60;

  static const char bands[] = "CDEFGHJKLMNPQRSTUVWX";
  int band_idx = (int)floor((lat + 80.0) / 8.0);
  if (band_idx > 19) band_idx = 19;

  // --- geographic -> UTM (k0 = 0.9996) ---
  const double a = 6378137.0, f = 1.0 / 298.257223563;
  const double k0 = 0.9996, E0 = 500000.0;
  const double n = f / (2.0 - f);
  const double A = a / (1.0 + n) * (1.0 + n * n / 4.0 + n * n * n * n / 64.0);
  const double a1 = n / 2.0 - 2.0 * n * n / 3.0 + 5.0 * n * n * n / 16.0;
  const double a2 = 13.0 * n * n / 48.0 - 3.0 * n * n * n / 5.0;
  const double a3 = 61.0 * n * n * n / 240.0;
  const double e = sqrt(f * (2.0 - f));

  double lat_r = lat * M_PI / 180.0;
  double dlon = lon * M_PI / 180.0 - ((zone - 1) * 6 - 180 + 3) * M_PI / 180.0;
  double s = sin(lat_r);
  double t = sinh(atanh(s) - e * atanh(e * s));
  double xi_p = atan2(t, cos(dlon));
  double eta_p = asinh(sin(dlon) / sqrt(t * t + cos(dlon) * cos(dlon)));
  double xi = xi_p + a1 * sin(2 * xi_p) * cosh(2 * eta_p)
                   + a2 * sin(4 * xi_p) * cosh(4 * eta_p)
                   + a3 * sin(6 * xi_p) * cosh(6 * eta_p);
  double eta = eta_p + a1 * cos(2 * xi_p) * sinh(2 * eta_p)
                     + a2 * cos(4 * xi_p) * sinh(4 * eta_p)
                     + a3 * cos(6 * xi_p) * sinh(6 * eta_p);
  double easting = E0 + k0 * A * eta;
  double northing = k0 * A * xi;
  if (lat < 0) northing += 10000000.0;

  // --- UTM -> 100 km square letters (MGRS-A lettering scheme) ---
  static const char col_sets[3][9] = {"ABCDEFGH", "JKLMNPQR", "STUVWXYZ"};
  static const char row_letters[] = "ABCDEFGHJKLMNPQRSTUV";  // 20-letter cycle
  int col_idx = (int)floor(easting / 100000.0) - 1;          // cols 1..8 -> 0..7
  char col = col_sets[(zone - 1) % 3][((col_idx % 8) + 8) % 8];
  int row_idx = (int)floor(northing / 100000.0);
  if (zone % 2 == 0) row_idx += 5;                           // even zones offset
  char row = row_letters[((row_idx % 20) + 20) % 20];

  unsigned long e5 = (unsigned long)floor(easting) % 100000UL;
  unsigned long n5 = (unsigned long)floor(northing) % 100000UL;
  char tmp[32];
  int len = snprintf(tmp, sizeof(tmp), "%d%c%c%c%05lu%05lu",
                     zone, bands[band_idx], col, row, e5, n5);
  if (len <= 0 || (unsigned)len >= out_sz) return false;
  memcpy(out, tmp, len + 1);
  return true;
}

// The map-reading pair only: the 100 m grid square as "013-284"
// (first 3 digits of the easting and northing groups). 7 chars + NUL.
static bool mgrs_grid100(double lat, double lon, char* out, unsigned out_sz) {
  char full[16];
  if (out_sz < 8 || !mgrs_format(lat, lon, full, sizeof(full))) return false;
  // full is "<zone><band><colrow>EEEEENNNNN" — take the 10-digit tail
  unsigned len = 0;
  while (full[len]) len++;
  const char* tail = full + len - 10;
  snprintf(out, out_sz, "%.3s-%.3s", tail, tail + 5);
  return true;
}
