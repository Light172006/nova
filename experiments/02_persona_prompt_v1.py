import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Swap this for whichever Gemma checkpoint you're testing.
# "google/gemma-2-2b-it"   -> Gemma 2, 2B, instruction-tuned (closest match to "gemma 2B")
# "google/gemma-3-4b-it"   -> Gemma 3, 4B, instruction-tuned
MODEL_NAME = "google/gemma-2-2b-it"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def load_model():
    print(f"Loading {MODEL_NAME} on {DEVICE} ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        dtype=torch.bfloat16 if DEVICE == "cuda" else torch.float32,
        device_map="auto" if DEVICE == "cuda" else None,
    )
    if DEVICE == "cpu":
        model.to(DEVICE)
    model.eval()
    print("Model loaded.\n")
    return tokenizer, model


def build_prompt(tokenizer, context_window):
    """
    context_window is a dict shaped like:
    {
        "history": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."},
            ...
        ]
    }
    Uses the tokenizer's chat template so turn formatting matches
    however Gemma was actually trained to expect it.
    """
    return tokenizer.apply_chat_template(
        context_window["history"],
        tokenize=False,
        add_generation_prompt=True,
    )


def generate_reply(tokenizer, model, context_window, max_new_tokens=200):
    prompt_text = build_prompt(tokenizer, context_window)
    inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.8,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )

    # Only decode the newly generated tokens, not the whole prompt back.
    new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
    reply = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return reply.strip()


def main():
    print(f'divice : {DEVICE}')
    print("Type your message. Type 'exit' to quit, 'reset' to clear history.\n")

    tokenizer, model = load_model()

    # This dict is the "context window" for the whole session.
    # Everything that's been said, in order, lives here.
    with open('D:\\Nova\\agents\\chat\\persona_prompt_v1.txt' , 'r') as f:
        system_input = f.read()

    context_window = {"history": []}
    context_window["history"].append({"role": "user", "content": system_input})

    reply_f = generate_reply(tokenizer, model, context_window)

    context_window["history"].append({"role": "assistant", "content": reply_f})
    
    print(f"Nova: {reply_f}\n")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() == "exit":
            break
        if user_input.lower() == "reset":
            context_window["history"] = []
            context_window["history"].append({"role": "user", "content": system_input})
            context_window["history"].append({"role": "assistant", "content": reply_f})

            print("(context window cleared)\n")
            continue
        if not user_input:
            continue

        # Add the user's turn to the context window
        context_window["history"].append({"role": "user", "content": user_input})

        reply = generate_reply(tokenizer, model, context_window)

        # Add the model's turn to the context window too, so it's
        # remembered on the next loop iteration
        context_window["history"].append({"role": "assistant", "content": reply})

        print(f"Nova: {reply}\n")


if __name__ == "__main__":
    main()