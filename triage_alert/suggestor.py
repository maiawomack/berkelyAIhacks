import os
import json
from datetime import datetime
from uuid import uuid4

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
except ImportError:
    pass

from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from triage_logic import adapt_frame, check_significant_change, run_triage, client

last_scene_store = {}


def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.utcnow(), msg_id=uuid4(), content=content)


agent = Agent(
    name="triage_alert_agent",
    seed="triage_alert_seed_phrase",
    port=8001,
    endpoint=["http://localhost:8001/submit"],
    network="testnet",
)

protocol = Protocol(spec=chat_protocol_spec)

LAST_TRIAGE_KEY = "last_triage"
LAST_SCENE_KEY  = "last_scene"


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    text = msg.text()
    if not text:
        return

    try:
        incoming  = json.loads(text)
        frames    = incoming if isinstance(incoming, list) else [incoming]
        responses = []

        for frame in frames:
            # Auto-adapt if rich schema (has "people" array or "injuries" array)
            if "people" in frame or "injuries" in frame:
                frame = adapt_frame(frame)

            timestamp  = frame.get("timestamp", "unknown time")
            last_scene = last_scene_store.get(LAST_SCENE_KEY)

            if last_scene is None:
                should_alert  = True
                change_reason = "Initial scene assessment."
            else:
                change_check  = check_significant_change(last_scene, frame)
                should_alert  = change_check.get("significant_change", False)
                change_reason = change_check.get("reason", "")

            last_scene_store[LAST_SCENE_KEY] = frame

            # ← fixed: was outside the loop, causing only last frame to get a response
            if should_alert:
                triage_text = run_triage(json.dumps(frame))
                last_scene_store[LAST_TRIAGE_KEY] = triage_text
                confidence = frame.get("confidence", 1)
                flag = (
                    f"\n⚠️  LOW CONFIDENCE FRAME ({confidence:.0%}) — treat with caution."
                    if confidence < 0.3 else ""
                )
                responses.append(f"[{timestamp}]\n{triage_text}{flag}")
            else:
                responses.append(f"[{timestamp}] ✅ No change — {change_reason}")

        response = "\n\n---\n\n".join(responses)

    except json.JSONDecodeError:
        try:
            r = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system="You are a helpful emergency triage assistant. Answer dispatcher questions clearly and concisely.",
                messages=[{"role": "user", "content": text}],
            )
            response = r.content[0].text
        except Exception as e:
            response = f"Error processing question: {e}"

    except Exception as e:
        ctx.logger.exception("Error in triage processing")
        response = f"Triage error: {e}"

    await ctx.send(sender, create_text_chat(response))


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
