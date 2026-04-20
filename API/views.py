from rest_framework.decorators import api_view
from rest_framework.response import Response
from .ml.model import predict_admission

@api_view(['POST'])
def predict_admission_view(request):
    subjects = request.data.get('subjects', [])

    if not subjects:
        return Response({"error": "No subjects provided"}, status=400)

    # Grade → points mapping
    grade_map = {
        '1': 1, '2': 2, '3': 3,
        '4': 5, '5': 5,
        '6': 7, '7': 7,
        '8': 8, '9': 8,
        'U': 9
    }

    total_points = sum([grade_map.get(s['grade'], 9) for s in subjects])
    avg_points = total_points / len(subjects)

    prediction, probability = predict_admission(avg_points)

    return Response({
        "success": True,
        "average_points": avg_points,
        "prediction": int(prediction),
        "probability": float(probability),
        "message": "Likely Admitted" if prediction == 1 else "Low Chance"
    })