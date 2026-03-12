"""
Resubmit Matthew 12 to JSON2Video with fixed scene 20 text.
Uses existing Kling video URLs (no new credits burned).
Run: python workflows/biblical-cinematic/scripts/resubmit-matthew12.py
"""
import os
import json
import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
API_KEY = os.getenv("JSON2VIDEO_API_KEY")
if not API_KEY:
    raise SystemExit("ERROR: JSON2VIDEO_API_KEY not found in .env")

TEMPLATE_ID = "cHtpubYegDm2patG2tym"

# Original variables from the failed render — scene 19 text split to fill scene 20
variables = {
    "scene1_voiceOverText": "At that time, Jesus went on the Sabbath day through the corn, and his Disciples were an hungered, and began to pluck the ears of corn, and to eate.",
    "scene1_videoUrl": "https://v3b.fal.media/files/b/0a91c1af/0zIm8l_pBSPNWkkMOLuyE_output.mp4",
    "scene1_overlaidText": "Jesus went on the Sabbath day",
    "scene2_voiceOverText": "But when the Pharisees saw it, they said unto him, Behold, thy Disciples do that which is not lawful to do upon the Sabbath day.",
    "scene2_videoUrl": "https://v3b.fal.media/files/b/0a91c1b9/m1DMuiWXxTxzq91h0O6rp_output.mp4",
    "scene2_overlaidText": "Pharisees saw it and condemned",
    "scene3_voiceOverText": "But he said unto them, have ye not read what David did when he was an hungered, and they that were with him, How he entred into the house of God, and did eate the show bread, which was not lawful for him to eate, neither for them which were with him, but, only for the Priests?",
    "scene3_videoUrl": "https://v3b.fal.media/files/b/0a91c1c4/ESqmDOwWm5R0lG5OYCWXG_output.mp4",
    "scene3_overlaidText": "Have ye not read what David did",
    "scene4_voiceOverText": "Or have ye not read in the law, how that on the Sabbath days the Priests in the Temple profane the Sabbath, and are blameless?",
    "scene4_videoUrl": "https://v3b.fal.media/files/b/0a91c1d0/lH2mrTo7Cm29HFdbdl7jg_output.mp4",
    "scene4_overlaidText": "Priests profane the Sabbath blameless",
    "scene5_voiceOverText": "But I say unto you, that in this place is one greater then the Temple.",
    "scene5_videoUrl": "https://v3b.fal.media/files/b/0a91c1db/VcO3-CVOaYJDIrnAFlDqn_output.mp4",
    "scene5_overlaidText": "One greater than the Temple",
    "scene6_voiceOverText": "But if ye had known what this meaneth, I will have mercy, and not sacrifice, ye would not have condemned the guiltless.",
    "scene6_videoUrl": "https://v3b.fal.media/files/b/0a91c1e5/fEAGE1NIMpmGnjyhEP4IL_output.mp4",
    "scene6_overlaidText": "I will have mercy not sacrifice",
    "scene7_voiceOverText": "For the son of man is Lord even of the Sabbath day.",
    "scene7_videoUrl": "https://v3b.fal.media/files/b/0a91c1ef/J4sWu_5S_y6Sm0rZYpI-U_output.mp4",
    "scene7_overlaidText": "Son of man is Lord of Sabbath",
    "scene8_voiceOverText": "And when he was departed thence, he went into their Synagogue.",
    "scene8_videoUrl": "https://v3b.fal.media/files/b/0a91c1fa/tJdYDtymdPhYon06G3C2v_output.mp4",
    "scene8_overlaidText": "He went into their Synagogue",
    "scene9_voiceOverText": "And behold, there was a man which had his hand withered, and they asked him, saying, Is it lawful to heal on the Sabbath days? that they might accuse him.",
    "scene9_videoUrl": "https://v3b.fal.media/files/b/0a91c206/ckAQ3iy16CpIerqpdriuo_output.mp4",
    "scene9_overlaidText": "Man with withered hand present",
    "scene10_voiceOverText": "And he said unto them, What man shall there be among you, that shall have one sheep: and if it fall into a pit on the Sabbath day, will he not lay hold on it, and lift it out?",
    "scene10_videoUrl": "https://v3b.fal.media/files/b/0a91c210/t2tfkvhTXrqzutC2n96w__output.mp4",
    "scene10_overlaidText": "What man has one sheep in pit",
    "scene11_voiceOverText": "How much then is a man better then a sheep?",
    "scene11_videoUrl": "https://v3b.fal.media/files/b/0a91c21a/WYKQ9O4TM3zSKKCtMbq7k_output.mp4",
    "scene11_overlaidText": "Man is better than sheep",
    "scene12_voiceOverText": "Wherefore it is lawful to do well on the Sabbath days.",
    "scene12_videoUrl": "https://v3b.fal.media/files/b/0a91c226/7-TOd0xFutRl-8ETok4RW_output.mp4",
    "scene12_overlaidText": "Lawful to do well on Sabbath",
    "scene13_voiceOverText": "Then saith he to the man, Stretch forth thine hand: and he stretched it forth, and it was restored whole, like as the other.",
    "scene13_videoUrl": "https://v3b.fal.media/files/b/0a91c230/03q4MU3P48y4ul8MFN-eZ_output.mp4",
    "scene13_overlaidText": "Stretch forth thine hand",
    "scene14_voiceOverText": "Then the Pharisees went out, and held a counsel against him, how they might destroy him.",
    "scene14_videoUrl": "https://v3b.fal.media/files/b/0a91c23a/VZjilKJwNrmNI1TkludO2_output.mp4",
    "scene14_overlaidText": "Pharisees held counsel to destroy",
    "scene15_voiceOverText": "But when Jesus knew it, he withdrew himself from thence: and great multitudes followed him, and he healed them all, And charged them that they should not make him known:",
    "scene15_videoUrl": "https://v3b.fal.media/files/b/0a91c245/mEySDfSd2rJHRpWT8FbDT_output.mp4",
    "scene15_overlaidText": "Jesus withdrew with great multitudes",
    "scene16_voiceOverText": "That it might be fulfilled which was spoken by Isaiah the Prophet, saying, Behold, my servant whom I have chosen, my beloved in whom my soul is well pleased: I will put my spirit upon him, and he shall show judgment to the Gentiles.",
    "scene16_videoUrl": "https://v3b.fal.media/files/b/0a91c24f/1Xn8bAqlJzjBvJFSRvssa_output.mp4",
    "scene16_overlaidText": "Fulfilled by Isaiah the Prophet",
    "scene17_voiceOverText": "He shall not strive, nor cry, neither shall any man hear his voice in the streets. A bruised reed shall he not break, and smoking flax shall he not quench, till he send forth judgment unto victory.",
    "scene17_videoUrl": "https://v3b.fal.media/files/b/0a91c25a/-OWxe4_AqVBKqh4eWRpkH_output.mp4",
    "scene17_overlaidText": "Shall not strive nor cry out",
    "scene18_voiceOverText": "And in his name shall the Gentiles trust.",
    "scene18_videoUrl": "https://v3b.fal.media/files/b/0a91c266/px1DJDQN-L2b7NW75RtRX_output.mp4",
    "scene18_overlaidText": "Gentiles shall trust in his name",
    # FIXED: Split scene 19 to fill scene 20
    "scene19_voiceOverText": "Then was brought unto him one possessed with a devil, blind, and dumb: and he healed him, insomuch that the blind and dumb both spoke and saw.",
    "scene19_videoUrl": "https://v3b.fal.media/files/b/0a91c271/okHh7JG5pAuQK6sNlWTYu_output.mp4",
    "scene19_overlaidText": "Demon-possessed man healed and speaks",
    "scene20_voiceOverText": "And all the people were amazed, and said, Is this the son of David?",
    "scene20_videoUrl": "https://v3b.fal.media/files/b/0a91c271/okHh7JG5pAuQK6sNlWTYu_output.mp4",
    "scene20_overlaidText": "Is this the son of David",
    "totalScenes": 20,
}

# First check if fal.media URLs are still alive
print("Checking if video URLs are still valid...")
test_url = variables["scene1_videoUrl"]
resp = requests.head(test_url, timeout=10)
if resp.status_code != 200:
    raise SystemExit(f"ERROR: Video URLs have expired (got {resp.status_code}). You'll need to re-run the full workflow.")
print(f"URLs still valid (status {resp.status_code})")

# Submit to JSON2Video
print(f"\nSubmitting to JSON2Video (template: {TEMPLATE_ID})...")
payload = {
    "template": TEMPLATE_ID,
    "resolution": "hd",
    "quality": "high",
    "variables": variables,
}

resp = requests.post(
    "https://api.json2video.com/v2/movies",
    headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
    json=payload,
    timeout=30,
)

if resp.status_code != 200:
    print(f"ERROR {resp.status_code}: {resp.text}")
    raise SystemExit(1)

data = resp.json()
project_id = data.get("project", data.get("id", "unknown"))
print(f"Submitted! Project ID: {project_id}")
print(f"Check status at: https://api.json2video.com/v2/movies?project={project_id}")
print("Or check JSON2Video dashboard → Render logs")
