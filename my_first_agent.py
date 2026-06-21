import httpx
from uagents import Agent, Context, Model

class ChatMessage(Model):
    text: str

agent = Agent(
    name="Ananya",
    seed="secret_seed_phrase",
    port=8000,
    endpoint=["http://localhost:8000/submit"],
)

VISION_SERVER = "https://superglue-arguably-croon.ngrok-free.dev"

@agent.on_event("startup")
async def startup_function(ctx: Context):
    ctx.logger.info(f"Dispatch AI started. Address: {agent.address}")

@agent.on_message(model=ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Emergency message: {msg.text}")
    
    # Get the public session URL from the vision server
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{VISION_SERVER}/server-url", timeout=5)
            data = resp.json()
            url = data.get("url", VISION_SERVER)
    except:
        url = VISION_SERVER

    session_link = f"{url}/capture.html"

    await ctx.send(sender, ChatMessage(
        text=(
            f"🚨 DISPATCH AI ACTIVATED\n\n"
            f"Emergency received. Sending video link to caller now.\n\n"
            f"📹 Camera link: {session_link}\n\n"
            f"Our vision agent is analyzing the scene in real time. "
            f"A structured dispatch brief will populate on the dispatcher dashboard shortly."
        )
    ))

if __name__ == "__main__":
    agent.run()