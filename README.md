# python
Python Scripts

Bu repo içindeki script'ler farklı otomasyon ihtiyaçları için örnekler içerir.

## Yeni: Aktivite izleme servisi (MVP)

`activity_monitor.py` ile bilgisayardaki kullanım istatistiklerini yerel olarak toplayabilirsiniz:

- Hangi uygulama ne kadar süre aktif kullanılmış
- Kaç kez mouse tıklanmış
- Kaç kez klavye tuşuna basılmış
- Basit yanıt hızı metriği (girdi olayları arası ortalama süre)
- Markdown / JSON rapor çıktısı

### Kurulum

```bash
pip install psutil pynput
```

> Linux tarafında aktif pencere tespiti için `xdotool` önerilir.

### İzlemeyi başlatma

```bash
python activity_monitor.py start --db data/activity_stats.db
```

Opsiyonel parametreler:

- `--sample-interval`: aktif pencere örnekleme aralığı (sn)
- `--flush-interval`: input istatistiklerini DB'ye yazma aralığı (sn)

### Rapor üretme

```bash
python activity_monitor.py report --db data/activity_stats.db --out reports/daily_report.md
```

JSON çıktısı için:

```bash
python activity_monitor.py report --db data/activity_stats.db --out reports/daily_report.json
```

Belirli tarih aralığı (ISO format):

```bash
python activity_monitor.py report \
  --db data/activity_stats.db \
  --start 2026-02-25T09:00:00 \
  --end 2026-02-25T18:00:00
```

## Notlar

- Bu çözüm bir MVP'dir; kurumsal kullanım için KVKK/GDPR uyumu, açık rıza, log güvenliği ve veri saklama politikaları eklenmelidir.
- Bu repo ayrıca XLSX/TXT içinde `@gmail.com` araması yapan script de içerir (`file_and_folder_gmail_account_finder.py`).
