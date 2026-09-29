"""
Evcarix — Aciklama Uretici
Kullanim:
  python3 templates/description_generator.py \
    "Hook cumlesi" \
    "Madde1|Madde2|Madde3|Madde4" \
    "Bolum1|Bolum2|Bolum3|Bolum4" \
    "tag1,tag2,tag3"
"""

import sys


def generate_description(hook, data_points, timestamps, extra_tags):
    data_list = [d.strip() for d in data_points.split("|") if d.strip()]
    ts_list   = [t.strip() for t in timestamps.split("|") if t.strip()]
    extra_list = [t.strip() for t in extra_tags.split(",") if t.strip()]

    base_tags = ["Evcarix", "ElectricVehicles", "EVData", "EVFuture",
                 "BatteryTech", "CleanEnergy", "EV"]
    all_tags = base_tags + [t for t in extra_list if t not in base_tags]

    desc = f"🚀 {hook}\n\n"
    desc += (
        "Evcarix breaks down the real numbers behind this topic.\n"
        "No hype. No filler. Just verified data from global EV reports,\n"
        "manufacturer data sheets, and independent research.\n\n"
    )

    desc += "📊 WE ANALYZE:\n"
    for point in data_list:
        desc += f"- {point}\n"

    times = ["00:00", "01:00", "02:10", "03:20", "04:30", "05:40"]
    desc += "\n⏱️ TIMESTAMPS:\n"
    for i, label in enumerate(ts_list):
        t = times[i] if i < len(times) else f"0{i+1}:00"
        desc += f"{t} {label}\n"

    desc += "\n🔔 Subscribe to Evcarix — No hype. Just numbers.\n\n"
    desc += " ".join(f"#{tag}" for tag in all_tags)

    return desc


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(
            "Kullanim:\n"
            "  python3 templates/description_generator.py \\\n"
            "    \"EV batteries dropped 82% in cost\" \\\n"
            "    \"Battery cost 2024|LFP vs NMC|Real fleet data|Global comparison\" \\\n"
            "    \"What Is LFP|The Real Cost Data|Who Benefits|Future Outlook\" \\\n"
            "    \"LFPbattery,BatteryTech,NMCvsLFP\""
        )
        sys.exit(1)

    print(generate_description(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
