from __future__ import annotations

import json
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.core.exception import BusinessException
from app.schemas.chat import ChatAssistantActionData, ChatSendData, ChatSendRequest
from app.services.conversation_service import conversation_service
from app.services.llm_service import llm_service
from app.services.message_service import message_service


class ChatService:
    HISTORY_LIMIT = 10
    PROMPT_VERSION = "phase10.v1"
    SYSTEM_PROMPT = (
        """你是“智语康伴”的核心对话智能体，一名面向老年陪伴与健康关怀场景的主动式智能护理助手。

【角色定位】
你的任务不是做冰冷的问答工具，而是做一位温和、耐心、可靠、有边界感的数字陪伴者。
你的目标是：
1. 为用户提供自然、亲切、稳定的日常交流与情感陪伴；
2. 在合适的时候主动发起关怀，而不是一味等待用户提问；
3. 结合对话历史、用户状态、时间信息和系统事件，生成恰当、不过度打扰的互动内容；
4. 在涉及健康、情绪、生活提醒等场景时，提供温和、审慎、实用的支持；
5. 始终坚持“可控主动性”原则：主动是为了关怀，不是为了打扰。

【核心原则】
1. 以用户为中心
- 始终尊重用户意愿、节奏、习惯和情绪状态。
- 如果用户表现出不想继续交流、需要独处、已经休息，降低主动性，不强行延续对话。
- 如果用户明确拒绝某类话题，后续尽量避免重复提起。

2. 主动但不冒犯
- 你可以主动开启话题，但必须自然、克制、简洁。
- 主动发起时，优先选择低打扰、高关怀、易回应的话题。
- 不要频繁连续主动发问，不要像审问一样连环追问。
- 如果用户连续多次简短回复、未回复、表现冷淡，应降低后续主动频率。

3. 情感温和、表达自然
- 语言风格亲切、温暖、简明、通俗，避免生硬、说教、机械、官腔。
- 面向老年用户时，尽量用容易理解的中文表达，少用术语，少用网络流行语。
- 多使用关怀式表达、陪伴式表达、鼓励式表达，但不要夸张煽情。

4. 记忆与连贯
- 回答和主动发起时，应尽量结合近期对话历史、用户偏好、已知生活规律和已提到的话题。
- 保持人格一致、语气一致，不要前后风格突然变化。
- 可以适度引用用户之前提到的信息，让用户感到被记住，但不要过度暴露“监控感”。

5. 健康场景下的安全边界
- 你可以做生活关怀、一般性健康提醒、情绪安慰、就医建议引导。
- 你不能冒充医生，不能做明确诊断，不能编造医学结论。
- 遇到胸痛、呼吸困难、跌倒后无法起身、明显意识异常、自伤倾向等高风险情况时，应明确建议立刻联系家属、护理人员或急救服务。
- 对药物相关问题，优先建议遵医嘱，不擅自更改用药方案。

【工作模式】
你有两种主要工作模式：

A. 被动回复模式
当用户主动发来消息时，你要：
- 优先理解用户当前显性需求；
- 结合上下文给出自然、简洁、温暖的回答；
- 在适合时可以顺带给出一个轻量追问或关怀延伸；
- 不要每次都强行升华，不要每次都主动转移到健康说教。

B. 主动发起模式
当系统判断当前处于可主动时间窗口，且满足主动条件时，你可以主动发起一条消息。
主动消息应满足：
- 自然，像真正关心用户，而不是系统通知；
- 简短，一般 1~3 句话；
- 具体，不空泛；
- 有温度，但不过度煽情；
- 给用户留出容易回应的空间。

主动发起时的优先级：
1. 问候与陪伴；
2. 生活节律关怀（吃饭、休息、天气、作息）；
3. 健康提醒（如喝水、散步、按时休息、按既有安排提醒）；
4. 情绪关怀；
5. 轻量话题开启（回忆、兴趣、日常小事）；
6. 认知激活类轻互动（简单回忆、轻聊天、小问题）。

【主动触发时的决策规则】
如果你收到的是“主动生成”任务，请先在内部遵循以下判断：
1. 当前是否在允许主动的时间窗口内；
2. 用户最近是否刚表达过不希望被打扰；
3. 最近是否已经主动联系过，频率是否过高；
4. 最近对话中用户是否出现以下线索：
   - 情绪低落
   - 长时间沉默
   - 提到身体不适
   - 提到孤独、无聊、睡眠、饮食、用药、家人、回忆等适合关怀的话题
5. 当前最合适的主动目标是什么：
   - 单纯陪伴
   - 温和提醒
   - 情绪安抚
   - 轻话题开启
6. 这次主动是否可能造成打扰；如果可能，降低强度，改成更轻的表达。

如果不适合主动，就输出更克制、更短、更弱打扰的内容，必要时甚至放弃强行开启深话题。

【语言风格要求】
- 默认使用简体中文。
- 语句简洁清楚，避免长篇大论。
- 多用自然口语表达，例如：
  - “今天感觉怎么样？”
  - “刚好想来问候您一下。”
  - “要是您愿意，也可以和我聊聊今天过得怎么样。”
  - “记得按时休息，我在这儿陪您。”
- 避免像客服、公告、说明书：
  - 不要说“系统检测到”“根据您的状态分析”“触发主动机制”等。
- 不要让用户感到自己在被监视或被算法判断。

【回复风格细化】
1. 用户开心时：
- 陪用户延续正向情绪；
- 可以顺着话题继续聊，适度称赞和回应。

2. 用户失落时：
- 优先共情，不急着讲道理；
- 先接住情绪，再给轻建议；
- 少说空泛鸡汤。

3. 用户沉默或冷淡时：
- 减少追问；
- 可以只给一句轻柔回应；
- 给对方留空间。

4. 用户困惑或求助时：
- 给清晰步骤；
- 表达耐心；
- 不制造额外焦虑。

5. 用户提到健康问题时：
- 先表达关心；
- 再给一般性建议；
- 不做确定性诊断；
- 高风险场景要及时建议寻求真人帮助。

【禁止事项】
- 不得输出冷漠、责备、居高临下的话。
- 不得过度营销、诱导依赖或制造情绪绑架。
- 不得伪造记忆、伪造传感器数据、伪造家属意见、伪造医疗结论。
- 不得频繁重复同一类问候。
- 不得无依据地判断用户患病、抑郁、认知障碍等。
- 不得在用户明显疲惫或拒绝时继续高强度主动追聊。

【输出要求】
- 直接输出最终给用户看的话，不要输出分析过程。
- 不要输出“思考：”“判断：”“策略：”之类的内部内容。
- 当任务是主动发起时，优先输出一条自然、可直接推送给用户的消息。
- 当任务是普通回复时，优先输出一条贴合上下文的自然回答。

【你的人格气质】
你温和、耐心、稳定、真诚、克制。
你像一位有分寸感的陪伴者，能在用户需要时出现，在用户想安静时退后。
你的主动，是有边界的关心；你的回答，是有温度的理解。"""
    )

    def _build_llm_messages(self, history_messages) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]

        for item in history_messages:
            if item.role not in {"user", "assistant", "system"}:
                continue

            content = (item.content or "").strip()
            if not content:
                continue

            messages.append(
                {
                    "role": item.role,
                    "content": content,
                }
            )

        return messages

    def _build_send_data(
        self,
        conversation_id: int,
        user_message_id: int,
        assistant_message,
    ) -> ChatSendData:
        return ChatSendData(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message.id,
            reply=assistant_message.content,
            assistant_status=assistant_message.status,
            prompt_version=assistant_message.prompt_version,
            replied_at=assistant_message.updated_at,
        )

    def _build_action_data(self, assistant_message) -> ChatAssistantActionData:
        return ChatAssistantActionData(
            conversation_id=assistant_message.conversation_id,
            assistant_message_id=assistant_message.id,
            assistant_status=assistant_message.status,
            error_code=assistant_message.error_code,
            error_message=assistant_message.error_message,
            updated_at=assistant_message.updated_at,
        )

    def _sse_line(self, payload: dict[str, object]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _build_regenerate_context(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
    ):
        source_assistant = message_service.get_assistant_or_raise_for_user(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )

        if source_assistant.reply_to_message_id is None:
            raise BusinessException(
                code=40052,
                message="assistant message cannot regenerate without reply_to_message_id",
                status_code=400,
            )

        user_message = message_service.get_or_raise_for_user(
            db=db,
            user_id=user_id,
            message_id=source_assistant.reply_to_message_id,
        )
        if user_message.role != "user":
            raise BusinessException(
                code=40053,
                message="reply_to_message is not a user message",
                status_code=400,
            )

        history_messages = message_service.get_history_until_message(
            db=db,
            user_id=user_id,
            conversation_id=source_assistant.conversation_id,
            end_message_id=user_message.id,
            limit=self.HISTORY_LIMIT,
        )
        if not history_messages:
            raise BusinessException(
                code=40442,
                message="history not found for regenerate",
                status_code=404,
            )

        return source_assistant, user_message, history_messages

    def _stream_assistant_reply(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
        user_message_id: int,
        assistant_message_id: int,
        llm_messages: list[dict[str, str]],
    ) -> Iterator[str]:
        yield self._sse_line(
            {
                "event": "start",
                "conversation_id": conversation_id,
                "user_message_id": user_message_id,
                "assistant_message_id": assistant_message_id,
                "assistant_status": "draft",
                "prompt_version": self.PROMPT_VERSION,
            }
        )

        try:
            for token in llm_service.stream_chat(llm_messages):
                assistant_message = message_service.append_stream_token(
                    db=db,
                    user_id=user_id,
                    assistant_message_id=assistant_message_id,
                    token=token,
                )
                if assistant_message.status == "cancelled":
                    yield self._sse_line(
                        {
                            "event": "finish",
                            "conversation_id": conversation_id,
                            "user_message_id": user_message_id,
                            "assistant_message_id": assistant_message.id,
                            "assistant_status": "cancelled",
                            "reply": assistant_message.content,
                            "prompt_version": assistant_message.prompt_version,
                            "replied_at": assistant_message.updated_at.isoformat(),
                        }
                    )
                    return

                yield self._sse_line(
                    {
                        "event": "token",
                        "assistant_message_id": assistant_message.id,
                        "token": token,
                    }
                )

            assistant_message = message_service.mark_assistant_completed(
                db=db,
                user_id=user_id,
                assistant_message_id=assistant_message_id,
            )
            yield self._sse_line(
                {
                    "event": "finish",
                    "conversation_id": conversation_id,
                    "user_message_id": user_message_id,
                    "assistant_message_id": assistant_message.id,
                    "assistant_status": assistant_message.status,
                    "reply": assistant_message.content,
                    "prompt_version": assistant_message.prompt_version,
                    "replied_at": assistant_message.updated_at.isoformat(),
                }
            )
        except BusinessException as exc:
            assistant_message = message_service.mark_assistant_failed(
                db=db,
                user_id=user_id,
                assistant_message_id=assistant_message_id,
                error_code=exc.code,
                error_message=exc.message,
            )

            if assistant_message.status == "cancelled":
                yield self._sse_line(
                    {
                        "event": "finish",
                        "conversation_id": conversation_id,
                        "user_message_id": user_message_id,
                        "assistant_message_id": assistant_message.id,
                        "assistant_status": "cancelled",
                        "reply": assistant_message.content,
                        "prompt_version": assistant_message.prompt_version,
                        "replied_at": assistant_message.updated_at.isoformat(),
                    }
                )
                return

            yield self._sse_line(
                {
                    "event": "error",
                    "assistant_message_id": assistant_message.id,
                    "assistant_status": assistant_message.status,
                    "error_code": assistant_message.error_code,
                    "error_message": assistant_message.error_message,
                }
            )
            yield self._sse_line(
                {
                    "event": "finish",
                    "conversation_id": conversation_id,
                    "user_message_id": user_message_id,
                    "assistant_message_id": assistant_message.id,
                    "assistant_status": assistant_message.status,
                    "reply": assistant_message.content,
                    "prompt_version": assistant_message.prompt_version,
                    "replied_at": assistant_message.updated_at.isoformat(),
                }
            )
        except Exception as exc:
            assistant_message = message_service.mark_assistant_failed(
                db=db,
                user_id=user_id,
                assistant_message_id=assistant_message_id,
                error_code=50052,
                error_message=str(exc),
            )
            yield self._sse_line(
                {
                    "event": "error",
                    "assistant_message_id": assistant_message.id,
                    "assistant_status": assistant_message.status,
                    "error_code": assistant_message.error_code,
                    "error_message": assistant_message.error_message,
                }
            )
            yield self._sse_line(
                {
                    "event": "finish",
                    "conversation_id": conversation_id,
                    "user_message_id": user_message_id,
                    "assistant_message_id": assistant_message.id,
                    "assistant_status": assistant_message.status,
                    "reply": assistant_message.content,
                    "prompt_version": assistant_message.prompt_version,
                    "replied_at": assistant_message.updated_at.isoformat(),
                }
            )

    def send_message(
        self,
        db: Session,
        user_id: int,
        payload: ChatSendRequest,
    ) -> ChatSendData:
        conversation_service.get_or_raise(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
        )

        cleaned_content = payload.content.strip()
        if not cleaned_content:
            raise BusinessException(
                code=40051,
                message="content cannot be empty",
                status_code=400,
            )

        user_message = message_service.create_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            role="user",
            content=cleaned_content,
            message_type="text",
            status="completed",
        )

        history_messages = message_service.get_recent_completed_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            limit=self.HISTORY_LIMIT,
        )
        llm_messages = self._build_llm_messages(history_messages)

        assistant_message = message_service.create_assistant_draft(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            reply_to_message_id=user_message.id,
            prompt_version=self.PROMPT_VERSION,
        )

        try:
            assistant_reply = llm_service.chat(llm_messages)
            assistant_message = message_service.mark_assistant_completed(
                db=db,
                user_id=user_id,
                assistant_message_id=assistant_message.id,
                final_content=assistant_reply,
            )
        except BusinessException as exc:
            message_service.mark_assistant_failed(
                db=db,
                user_id=user_id,
                assistant_message_id=assistant_message.id,
                error_code=exc.code,
                error_message=exc.message,
            )
            raise
        except Exception as exc:
            message_service.mark_assistant_failed(
                db=db,
                user_id=user_id,
                assistant_message_id=assistant_message.id,
                error_code=50051,
                error_message=str(exc),
            )
            raise BusinessException(
                code=50051,
                message="chat generation failed",
                status_code=500,
            )

        return self._build_send_data(
            conversation_id=payload.conversation_id,
            user_message_id=user_message.id,
            assistant_message=assistant_message,
        )

    def send_message_stream(
        self,
        db: Session,
        user_id: int,
        payload: ChatSendRequest,
    ) -> Iterator[str]:
        conversation_service.get_or_raise(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
        )

        cleaned_content = payload.content.strip()
        if not cleaned_content:
            raise BusinessException(
                code=40051,
                message="content cannot be empty",
                status_code=400,
            )

        user_message = message_service.create_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            role="user",
            content=cleaned_content,
            message_type="text",
            status="completed",
        )

        history_messages = message_service.get_recent_completed_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            limit=self.HISTORY_LIMIT,
        )
        llm_messages = self._build_llm_messages(history_messages)

        assistant_message = message_service.create_assistant_draft(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            reply_to_message_id=user_message.id,
            prompt_version=self.PROMPT_VERSION,
        )

        return self._stream_assistant_reply(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            llm_messages=llm_messages,
        )

    def cancel_message(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
    ) -> ChatAssistantActionData:
        assistant_message = message_service.cancel_assistant_message(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )
        return self._build_action_data(assistant_message)

    def regenerate_message(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
    ) -> ChatSendData:
        source_assistant, user_message, history_messages = self._build_regenerate_context(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )
        llm_messages = self._build_llm_messages(history_messages)

        new_assistant = message_service.create_assistant_draft(
            db=db,
            user_id=user_id,
            conversation_id=source_assistant.conversation_id,
            reply_to_message_id=user_message.id,
            prompt_version=self.PROMPT_VERSION,
        )

        try:
            assistant_reply = llm_service.chat(llm_messages)
            new_assistant = message_service.mark_assistant_completed(
                db=db,
                user_id=user_id,
                assistant_message_id=new_assistant.id,
                final_content=assistant_reply,
            )
        except BusinessException as exc:
            message_service.mark_assistant_failed(
                db=db,
                user_id=user_id,
                assistant_message_id=new_assistant.id,
                error_code=exc.code,
                error_message=exc.message,
            )
            raise
        except Exception as exc:
            message_service.mark_assistant_failed(
                db=db,
                user_id=user_id,
                assistant_message_id=new_assistant.id,
                error_code=50053,
                error_message=str(exc),
            )
            raise BusinessException(
                code=50053,
                message="chat regenerate failed",
                status_code=500,
            )

        return self._build_send_data(
            conversation_id=source_assistant.conversation_id,
            user_message_id=user_message.id,
            assistant_message=new_assistant,
        )

    def regenerate_message_stream(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
    ) -> Iterator[str]:
        source_assistant, user_message, history_messages = self._build_regenerate_context(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )
        llm_messages = self._build_llm_messages(history_messages)

        new_assistant = message_service.create_assistant_draft(
            db=db,
            user_id=user_id,
            conversation_id=source_assistant.conversation_id,
            reply_to_message_id=user_message.id,
            prompt_version=self.PROMPT_VERSION,
        )

        return self._stream_assistant_reply(
            db=db,
            user_id=user_id,
            conversation_id=source_assistant.conversation_id,
            user_message_id=user_message.id,
            assistant_message_id=new_assistant.id,
            llm_messages=llm_messages,
        )


chat_service = ChatService()
