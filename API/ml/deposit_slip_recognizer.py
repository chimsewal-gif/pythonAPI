# /media/lewin/DATA1/fourthyear-project/API/API/ml/deposit_slip_recognizer.py
import cv2
import pytesseract
import re
import numpy as np
import logging
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass
import pdf2image
from PIL import Image
import io
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)

@dataclass
class DepositSlipData:
    """Extracted deposit slip data"""
    reference_number: Optional[str] = None
    amount: Optional[float] = None
    account_number: Optional[str] = None
    depositor_name: Optional[str] = None
    bank_name: Optional[str] = None
    transaction_date: Optional[str] = None
    branch_name: Optional[str] = None
    confidence_score: float = 0.0

class DepositSlipRecognizer:
    """OCR-based deposit slip recognizer for Malawi banks"""
    
    def __init__(self):
        # Malawi bank patterns
        self.bank_patterns = {
            'National Bank of Malawi': ['national bank', 'nbm', 'national bank of malawi'],
            'Standard Bank Malawi': ['standard bank', 'standard bank malawi', 'standard'],
            'FDH Bank': ['fdh bank', 'fdh', 'first discount house'],
            'MyBucks Banking': ['mybucks', 'my bucks', 'mybucks banking'],
            'EcoBank Malawi': ['ecobank', 'ecobank malawi', 'eco bank'],
            'NBS Bank': ['nbs bank', 'nbs'],
            'Opportunity Bank': ['opportunity bank', 'opportunity']
        }
        
        # Regex patterns for extraction
        self.patterns = {
            'reference': [
                r'(?:REF|REFERENCE|TRANSACTION REF|TXN REF)[:\s]*([A-Z0-9\-]{6,25})',
                r'(?:TRX|TRANSACTION ID|TXN ID)[:\s]*([A-Z0-9\-]{6,25})',
                r'Payment Reference[:\s]*([A-Z0-9\-]{6,25})',
                r'([A-Z0-9]{8,20})'
            ],
            'amount': [
                r'(?:AMOUNT|TOTAL|AMOUNT PAID)[:\s]*MWK[:\s]*([0-9,]+(?:\.[0-9]{2})?)',
                r'MWK[:\s]*([0-9,]+(?:\.[0-9]{2})?)',
                r'([0-9,]+(?:\.[0-9]{2})?)\s*(?:MWK|KWACHA)',
                r'([0-9,]+)\s*\.\s*00'
            ],
            'account': [
                r'(?:ACCOUNT|A/C|ACCOUNT NO)[:\s#]*([0-9]{8,16})',
                r'A/C\s*:?\s*([0-9]{8,16})',
                r'([0-9]{10,14})'
            ],
            'depositor': [
                r'(?:DEPOSITOR|PAID BY|FROM)[:\s]*([A-Za-z\s\.]{3,50})',
                r'NAME[:\s]*([A-Za-z\s\.]{3,50})',
                r'CUSTOMER[:\s]*([A-Za-z\s\.]{3,50})'
            ],
            'date': [
                r'(?:DATE|TRANSACTION DATE)[:\s]*([0-9]{2}[/\-][0-9]{2}[/\-][0-9]{2,4})',
                r'([0-9]{2}[/\-][0-9]{2}[/\-][0-9]{2,4})'
            ],
            'branch': [
                r'(?:BRANCH)[:\s]*([A-Za-z\s]{3,30})',
                r'([A-Za-z]+\s+(?:BRANCH))'
            ]
        }
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Apply adaptive thresholding
        processed = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Denoise
        processed = cv2.medianBlur(processed, 3)
        
        return processed
    
    def extract_text(self, image: np.ndarray) -> str:
        """Extract text using Tesseract OCR"""
        config = r'--oem 3 --psm 6 -l eng'
        text = pytesseract.image_to_string(image, config=config)
        return text
    
    def extract_fields(self, text: str) -> Dict:
        """Extract fields using regex"""
        extracted = {}
        
        for field, patterns in self.patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    value = matches[0].strip()
                    if value and len(value) > 2:
                        extracted[field] = value
                        break
        
        return extracted
    
    def identify_bank(self, text: str) -> Optional[str]:
        """Identify bank from text"""
        text_lower = text.lower()
        for bank, keywords in self.bank_patterns.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return bank
        return None
    
    def clean_amount(self, amount_str: str) -> Optional[float]:
        """Convert amount string to float"""
        try:
            cleaned = amount_str.replace(',', '').replace(' ', '')
            return float(cleaned)
        except:
            return None
    
    def calculate_confidence(self, extracted: Dict, bank_found: bool) -> float:
        """Calculate confidence score"""
        score = 0.0
        total = 5  # reference, amount, account, depositor, bank
        
        if extracted.get('reference'):
            score += 1
        if extracted.get('amount'):
            score += 1
        if extracted.get('account'):
            score += 1
        if extracted.get('depositor'):
            score += 0.5
        if bank_found:
            score += 0.5
        
        return min(score / total, 1.0)
    
    def recognize(self, file) -> Dict[str, Any]:
        """Main recognition method"""
        try:
            # Handle different file types
            if hasattr(file, 'read'):  # Uploaded file
                file_bytes = file.read()
                file.seek(0)
                
                # Check if PDF
                if file.name and file.name.lower().endswith('.pdf'):
                    images = pdf2image.convert_from_bytes(file_bytes, dpi=300)
                    if not images:
                        return {'success': False, 'error': 'Could not process PDF'}
                    img = np.array(images[0])
                else:
                    # Process as image
                    nparr = np.frombuffer(file_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            else:
                img = file  # Already numpy array
            
            # Preprocess and extract text
            processed = self.preprocess_image(img)
            text = self.extract_text(processed)
            
            if not text.strip():
                return {
                    'success': False,
                    'error': 'No text could be extracted',
                    'extracted_data': None
                }
            
            # Extract data
            extracted = self.extract_fields(text)
            bank = self.identify_bank(text)
            
            # Clean amount
            amount = None
            if extracted.get('amount'):
                amount = self.clean_amount(extracted['amount'])
            
            # Calculate confidence
            confidence = self.calculate_confidence(extracted, bank is not None)
            
            result = {
                'success': True,
                'extracted_data': {
                    'reference_number': extracted.get('reference'),
                    'amount': amount,
                    'account_number': extracted.get('account'),
                    'depositor_name': extracted.get('depositor'),
                    'bank_name': bank,
                    'transaction_date': extracted.get('date'),
                    'branch_name': extracted.get('branch'),
                    'confidence_score': confidence
                },
                'raw_text_preview': text[:500]
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Recognition error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'extracted_data': None
            }

# Singleton instance
deposit_slip_recognizer = DepositSlipRecognizer()