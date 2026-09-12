import asyncio
import edge_tts

async def test():
    communicate = edge_tts.Communicate("Hello world. This is a test.", "en-US-JennyNeural")
    await communicate.save("test_tts.mp3")
    print("TTS OK - test_tts.mp3 created")

asyncio.run(test())
