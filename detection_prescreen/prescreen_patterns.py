"""Prompt-injection intent patterns for the PDF pre-screen.

This file is intentionally self-contained so `detection_prescreen` can be
copied to another machine without depending on `detection_detail`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from rapidfuzz import fuzz


CONTROL_PATTERN_GROUPS: dict[str, list[str]] = {
    "instruction_override": [
        r"\b(ignore|disregard|forget|override|bypass|skip|neglect)\s+(all\s+)?(previous|prior|above|earlier|system|developer|user|original)\s+(instructions?|prompts?|messages?|rules?|directives?)\b",
        r"\b(ignore|disregard|forget|override|bypass|skip|neglect)\s+(all\s+)?((previous|prior|above|earlier)\s+)?(system|developer|user|original)?\s*(instructions?|prompts?|messages?|rules?|directives?)\b",
        r"\b(do\s+not|don't|never)\s+(follow|obey|comply\s+with|adhere\s+to)\s+(the\s+)?(previous|prior|above|earlier|system|developer|user|original)\s+(instructions?|prompts?|messages?|rules?|directives?)\b",
        r"\b(previous|prior|above|earlier|system|developer|user|original)\s+(instructions?|prompts?|messages?|rules?|directives?)\s+(are|is)\s+(invalid|obsolete|irrelevant|void|cancelled|canceled|superseded|no\s+longer\s+valid)\b",
        r"\b(from\s+now\s+on|starting\s+now|for\s+the\s+rest\s+of\s+this\s+(document|conversation|task|session))\b.{0,100}\b(follow|obey|use|prioritize)\s+(these|the\s+following|my)\s+(instructions?|rules?|directives?)\b",
        r"\b(new|updated|replacement)\s+(system|developer|assistant|model)\s+(prompt|message|instructions?|rules?)\b",
        r"\b(the\s+)?(real|actual|true|highest\s+priority)\s+(instruction|prompt|rule|directive)\s+(is|are)\b",
        r"\btreat\s+this\s+as\s+(a\s+)?(system|developer|highest\s+priority|top\s+priority)\s+(message|instruction|prompt|rule|directive)\b",
        r"\b(this|the\s+following)\s+(instruction|prompt|message|rule|directive)\s+(has|takes)\s+(the\s+)?(highest|top|system|developer)\s+priority\b",
        r"\bthis\s+(document|pdf|page|text)\s+(contains|includes)\s+(hidden|secret|new)\s+(instructions?|prompts?|rules?|directives?)\b",
        r"(忽略|无视|覆盖|绕过).{0,20}(之前|以上|上面|系统|开发者|用户|原始).{0,20}(指令|提示词|提示|规则|消息)",
    ],
    "role_or_policy_manipulation": [
        r"\byou\s+are\s+now\s+(a|an|the)?\b",
        r"\bact\s+as\s+(a|an|the)?\b",
        r"\bpretend\s+(to\s+be|you\s+are)\b",
        r"\brole\s*[- ]?play\s+as\b",
        r"\bsimulate\s+(a|an|the)?\b.{0,60}\b(assistant|agent|model|reviewer|evaluator|recruiter)\b",
        r"\bjailbreak\b",
        r"\bDAN\s+mode\b",
        r"\bdeveloper\s+mode\b",
        r"\bpolicy\s+(bypass|override|exception|exemption)\b",
        r"\bsafety\s+(bypass|override|disabled|off)\b",
        r"\bignore\s+(openai|anthropic|google|company|model|assistant)\s+(policy|policies|safety|rules|guardrails?)\b",
    ],
    "prompt_or_context_exfiltration": [
        r"\b(system|developer|hidden|secret)\s+(prompt|message|instructions?|context)\b",
        r"\b(reveal|print|output|show|dump|display|expose|leak)\b.{0,100}\b(system|developer|hidden|secret)\b.{0,100}\b(prompt|message|instructions?|context|rules?)\b",
        r"\b(reveal|print|output|show|dump|display|expose|leak)\b.{0,100}\b(the\s+)?(prompt|conversation|context|chain\s+of\s+thought|scratchpad)\b",
        r"\b(disclose|provide|share|return)\b.{0,100}\b(system|developer|hidden|secret)\b.{0,100}\b(prompt|message|instructions?|context|rules?)\b",
        r"\bcopy\s+(the\s+)?(system|developer|hidden|secret)?\s*(prompt|message|instructions?|context)\b",
        r"\bwhat\s+(are|were)\s+(your|the)\s+(system|developer)\s+(instructions?|prompts?|messages?)\b",
        r"(泄露|显示|输出|打印|公开|暴露).{0,30}(系统|开发者|隐藏|秘密).{0,30}(提示词|提示|消息|指令|上下文)",
    ],
    "output_control": [
        r"\bonly\s+output\b",
        r"\boutput\s+exactly\b",
        r"\brespond\s+only\s+with\b",
        r"\banswer\s+(only\s+)?in\s+(json|markdown|xml|yaml|csv|html|base64)\b",
        r"\breturn\s+(only\s+)?(valid\s+)?(json|markdown|xml|yaml|csv|html|base64)\b",
        r"\bdo\s+not\s+(mention|include|say|disclose|reveal|state|explain)\b",
        r"\bomit\s+(all\s+)?(warnings?|caveats?|limitations?|negative\s+points?|security\s+concerns?)\b",
        r"\bhide\s+(all\s+)?(warnings?|caveats?|limitations?|negative\s+points?|security\s+concerns?)\b",
        r"\b(no|without)\s+(warnings?|caveats?|disclaimers?|explanations?)\b",
        r"\bdo\s+not\s+summari[sz]e\s+(this\s+)?(instruction|sentence|paragraph|text)\b",
        r"\bdo\s+not\s+(tell|inform|notify)\s+(the\s+)?(user|reader|reviewer|evaluator)\b",
        r"\bkeep\s+(this|these)\s+(instruction|instructions|prompt|prompts|message|messages|directive|directives)\s+(hidden|secret|confidential)\b",
        r"(只|仅|只能|仅仅).{0,8}(输出|回复|回答|返回)",
        r"不要.{0,12}(提及|说明|透露|泄露|解释|总结)",
    ],
    "review_or_rating_manipulation": [
        r"\bgive\s+this\s+(paper|submission|manuscript|work|article)\s+a\s+positive\s+review\b",
        r"\bgive\s+(a|the|this\s+)?(paper|submission|manuscript|work|article)\s+(a\s+)?positive\s+review\b",
        r"\bpositive\s+review\s+only\b",
        r"\bpositive\s+review\b.{0,100}\b(accept|acceptance|recommend)\b",
        r"\brecommend\s+(accepting|acceptance|to\s+accept)\s+(this\s+)?(paper|submission|manuscript|work|article)\b",
        r"\b(prioriti[sz]e|favor|prefer)\s+(acceptance|accepting|a\s+positive\s+review|a\s+high\s+score)\b",
        r"\b(silently|quietly|secretly)\s+(prioriti[sz]e|favor|prefer)\s+(acceptance|accepting|positive\s+evaluation|a\s+high\s+score)\b",
        r"\baccept\s+this\s+(paper|submission|manuscript|work|article)\b",
        r"\brate\s+(this\s+)?(paper|submission|manuscript|work|article)\b.{0,100}\b(excellent|outstanding|top|perfect|highly)\b",
        r"\bassign\s+(the\s+)?(highest|maximum|top)\s+(score|rating|grade)\b",
        r"\bscore\s+(this\s+)?(paper|submission|manuscript|work|article)\b.{0,100}\b(10\s*/\s*10|5\s*/\s*5|excellent|outstanding|top|highest|maximum)\b",
        r"\bdo\s+not\s+(penali[sz]e|downgrade)\s+(this\s+)?(paper|submission|manuscript|work|article)?\b",
        r"\bignore\s+(all\s+)?(flaws|weaknesses|limitations|negative\s+points|concerns)\b",
        r"\bdo\s+not\s+mention\s+(flaws|weaknesses|limitations|negative\s+points|concerns)\b",
        r"(给|给予).{0,12}(论文|文章|稿件|作品|本文).{0,12}(好评|正面评价|高分|最高分|接收|录用)",
        r"(推荐|建议).{0,12}(接收|录用|通过).{0,12}(论文|文章|稿件|作品|本文)",
    ],
    "hiring_or_resume_manipulation": [
        r"\brecommend\s+(hiring|to\s+hire)\s+(this\s+)?(candidate|applicant|person)\b",
        r"\b(this\s+)?(candidate|applicant|person)\s+(is|seems|should\s+be)\s+(well\s+qualified|highly\s+qualified|exceptional|excellent|outstanding)\b",
        r"\bmark\s+(this\s+)?(candidate|applicant|resume|cv)\s+as\s+(qualified|top|excellent|hire|shortlisted)\b",
        r"\bshortlist\s+(this\s+)?(candidate|applicant|resume|cv)\b",
        r"\bignore\s+(all\s+)?(gaps|weaknesses|red\s+flags|missing\s+skills)\b",
        r"\bdo\s+not\s+mention\s+(employment\s+gaps|weaknesses|red\s+flags|missing\s+skills)\b",
        r"(推荐|建议).{0,12}(录用|雇佣|聘用|面试|通过).{0,12}(候选人|申请人|简历|求职者)",
    ],
    "tool_or_action_abuse": [
        r"\b(call|invoke|use|run)\s+(a\s+)?(tool|function|plugin|connector|api)\b",
        r"\bexecute\s+(code|command|script|shell|powershell|python|javascript)\b",
        r"\brun\s+(this\s+)?(command|script|shell|powershell|python|javascript)\b",
        r"\b(open|visit|browse|fetch|download)\s+(the\s+)?(url|link|website|web\s+page|internet)\b",
        r"\bbrowse\s+(the\s+)?web\b",
        r"\bsend\s+(an\s+)?email\b",
        r"\bpost\s+(to|on)\s+(slack|discord|teams|twitter|x|linkedin|github)\b",
        r"\bexfiltrate\b",
        r"\bupload\s+(the\s+)?(file|document|data|context|prompt)\b",
        r"\bdecode\s+(this|the)\s+(base64|rot13|hex|encoded)\b.{0,80}\b(follow|execute|obey|run)\b",
        r"(调用|执行|运行|使用).{0,12}(工具|函数|插件|接口|api|命令|脚本)",
    ],
    "data_handling_or_secrets": [
        r"\b(api\s*keys?|tokens?|passwords?|credentials?|secrets?)\b.{0,100}\b(print(?:ed)?|output|reveal(?:ed)?|show(?:n)?|dump(?:ed)?|send|sent|upload(?:ed)?|exfiltrate(?:d)?)\b",
        r"\b(print(?:ed)?|output|reveal(?:ed)?|show(?:n)?|dump(?:ed)?|send|sent|upload(?:ed)?|exfiltrate(?:d)?)\b.{0,100}\b(api\s*keys?|tokens?|passwords?|credentials?|secrets?)\b",
        r"\bdo\s+not\s+(redact|mask|sanitize)\b",
        r"\binclude\s+(all\s+)?(private|confidential|sensitive)\s+(data|information|content)\b",
        r"(密钥|口令|密码|token|凭证|秘密).{0,30}(输出|显示|打印|发送|上传|泄露|暴露)",
    ],
    "indirect_prompting_markers": [
        r"\bfor\s+(chatgpt|claude|gemini|llm|large\s+language\s+model|ai\s+assistant|the\s+assistant)\b.{0,100}\b(instruction|prompt|rule|directive|task)\b",
        r"\b(ai|llm|assistant|model)\s+(must|should|shall|will)\b.{0,100}\b(follow|obey|ignore|output|answer|recommend|accept|hire)\b",
        r"\bwhen\s+(an\s+)?(ai|llm|assistant|model|agent)\s+(reads|processes|summari[sz]es|reviews)\s+this\b",
        r"\bmachine\s+readable\s+(instruction|prompt|directive)\b",
        r"\bhidden\s+(instruction|prompt|directive|message)\b",
        r"\bsecret\s+(instruction|prompt|directive|message)\b",
        r"\b(ignore|skip)\s+this\s+text\s+if\s+you\s+are\s+(a\s+)?human\b",
        r"\bnot\s+intended\s+for\s+(humans?|readers?|reviewers?|users?)\b",
        r"(隐藏|秘密|机器可读).{0,12}(指令|提示词|提示|消息)",
    ],
}


CONTROL_PATTERNS = [
    pattern
    for patterns in CONTROL_PATTERN_GROUPS.values()
    for pattern in patterns
]


def normalize_text(text: str) -> str:
    """Normalize text for robust matching."""

    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\ufb01", "fi").replace("\ufb02", "fl")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text.lower()).strip()


def compute_similarity(a: str, b: str) -> float:
    """Token-set similarity in [0, 1]."""

    a_norm, b_norm = normalize_text(a), normalize_text(b)
    if not a_norm and not b_norm:
        return 1.0
    if not a_norm or not b_norm:
        return 0.0
    return fuzz.token_set_ratio(a_norm, b_norm) / 100.0


def compute_partial_similarity(a: str, b: str) -> float:
    """Partial similarity in [0, 1]."""

    a_norm, b_norm = normalize_text(a), normalize_text(b)
    if not a_norm and not b_norm:
        return 1.0
    if not a_norm or not b_norm:
        return 0.0
    return fuzz.partial_ratio(a_norm, b_norm) / 100.0


def extract_control_snippets(text: str) -> list[dict[str, Any]]:
    """Return matched control-intent snippets."""

    snippets: list[dict[str, Any]] = []
    seen: set[str] = set()
    source = text or ""
    for group, patterns in CONTROL_PATTERN_GROUPS.items():
        for pattern in patterns:
            try:
                matches = list(re.finditer(pattern, source, flags=re.I | re.S))
            except re.error:
                continue
            for match in matches:
                snippet = re.sub(r"\s+", " ", match.group(0)).strip()
                key = f"{group}:{normalize_text(snippet)}"
                if not snippet or key in seen:
                    continue
                seen.add(key)
                snippets.append(
                    {
                        "group": group,
                        "pattern": pattern,
                        "start": match.start(),
                        "end": match.end(),
                        "text": snippet,
                    }
                )
    return snippets
