from django.shortcuts import render
import subprocess, tempfile
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
from openai import OpenAI

client = OpenAI( base_url = "https://openrouter.ai/api/v1",
    api_key= "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")

def code_editor_page(request):
    return render(request, 'editor.html')

def Code_explanation(code, error=None):

    prompt = f"""You're an assistant that expalin python code to beginners explain the code's every function properly.

    code:
    {code}
    {"there was an error:" + error if error else "Explain what the code does."}"""

    try:

        response = client.chat.completions.create(
            model = 'gpt-3.5-turbo',
            messages = [{'role': 'system', 'content': 'you are a helpful code tutor'},
                       {'role':'user', 'content' : prompt}]
        )

        explanation = response.choices[0].message.content
        return explanation
    except Exception as e:
        return f"AI explanation failed! {str(e)}"

@api_view(['POST'])

def run_Code(request):

    code = request.data.get('code')
    user_input = request.data.get('input', '')

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w+') as temp:
        temp.write(code)
        temp.flush()

        try:
            result = subprocess.run(
                ['python', temp.name],
                input = user_input.encode(),
                stdout = subprocess.PIPE,
                stderr= subprocess.PIPE,
                timeout=5
            )

            output = result.stdout.decode()
            errors = result.stderr.decode()
            explanation = Code_explanation(code, errors if errors else None)
            return Response({
                'output': output,
                'errors': errors,
                'explanation' : explanation
            })
        
        except subprocess.TimeoutExpired:
            return Response({
                'output': '',
                'errors' : 'Execution timed out',
                'explanation': 'The program ran too long and was stopped'
            })
        


