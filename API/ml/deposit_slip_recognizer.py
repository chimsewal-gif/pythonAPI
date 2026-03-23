# /media/lewin/DATA1/fourthyear-project/API/API/ml/deposit_slip_recognizer.py

import cv2
import pytesseract
import re
import numpy as np
import logging
from typing import Dict, Optional, Any, Tuple, List
from dataclasses import dataclass, field
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
    source_of_funds: Optional[str] = None
    application_of_transaction: Optional[str] = None
    phone_number: Optional[str] = None


class DepositSlipRecognizer:
    """OCR-based deposit slip recognizer for Malawi banks"""
    
    def __init__(self):
        # Malawi bank patterns (expanded with NBS specific patterns)
        self.bank_patterns = {
            'NBS Bank': [
                'nbs bank', 'nbs', 'nbs bank plc', 'bic f d', 'bicfd',
                'cash deposit slip', 'nbs bank malawi'
            ],
            'National Bank of Malawi': [
                'national bank', 'nbm', 'national bank of malawi'
            ],
            'Standard Bank Malawi': [
                'standard bank', 'standard bank malawi', 'standard'
            ],
            'FDH Bank': [
                'fdh bank', 'fdh', 'first discount house'
            ],
            'MyBucks Banking': [
                'mybucks', 'my bucks', 'mybucks banking'
            ],
            'EcoBank Malawi': [
                'ecobank', 'ecobank malawi', 'eco bank'
            ],
            'Opportunity Bank': [
                'opportunity bank', 'opportunity'
            ]
        }
        
        # Enhanced regex patterns for extraction - specifically for NBS deposit slip
        self.patterns = {
            'reference': [
                r'(?:REF|REFERENCE|TRANSACTION REF|TXN REF|Deposit Reference|Reference No)[:\s]*([A-Z0-9\-]{6,25})',
                r'(?:TRX|TRANSACTION ID|TXN ID)[:\s]*([A-Z0-9\-]{6,25})',
                r'Payment Reference[:\s]*([A-Z0-9\-]{6,25})',
                r'Reference Number[:\s]*([A-Z0-9\-]{6,25})',
                r'([A-Z0-9]{8,20})',
                r'Deposit\s+Reference\s*:?\s*([A-Z0-9]+)',  # NBS specific
            ],
            'amount': [
                r'(?:AMOUNT|TOTAL|AMOUNT PAID|Amount Account|Drawn|Over)[:\s]*MWK[:\s]*([0-9,]+(?:\.[0-9]{2})?)',
                r'MWK[:\s]*([0-9,]+(?:\.[0-9]{2})?)',
                r'([0-9,]+(?:\.[0-9]{2})?)\s*(?:MWK|KWACHA)',
                r'([0-9,]+)\s*\.\s*00',
                r'Total[:\s]*([0-9,]+)',
                r'K\d+\s+(\d+)\s+(\d+)\s+(\d+)',  # For denomination table like K5000 | 2 00 0 00
                r'TOTAL[:\s]*\K([0-9\s]+)',  # Total field
            ],
            'account': [
                r'(?:ACCOUNT|A/C|ACCOUNT NO|Account Number)[:\s#]*([0-9]{8,16})',
                r'A/C\s*:?\s*([0-9]{8,16})',
                r'Account\s*Number[:\s]*([0-9]{8,16})',
                r'([0-9]{10,14})',
                r'Account\s+Number\s*:\s*(\d+)',  # NBS specific
            ],
            'depositor': [
                r'(?:DEPOSITOR|PAID BY|FROM|Depositor Name)[:\s]*([A-Za-z\s\.]{3,50})',
                r'NAME[:\s]*([A-Za-z\s\.]{3,50})',
                r'CUSTOMER[:\s]*([A-Za-z\s\.]{3,50})',
                r'Account\s*Name[:\s]*([A-Za-z\s]+)',
                r'Description by \(Name\)[:\s]*([A-Za-z\s]+)',  # NBS specific
                r'Account Name[:\s]*([A-Za-z\s]+)',  # NBS specific
            ],
            'date': [
                r'(?:DATE|TRANSACTION DATE|Date)[:\s]*([0-9]{2}[/\-][0-9]{2}[/\-][0-9]{2,4})',
                r'([0-9]{2}[/\-][0-9]{2}[/\-][0-9]{2,4})',
                r'Teller\'s Date Stamp[:\s]*([0-9]{2}[/\-][0-9]{2}[/\-][0-9]{2,4})',
                r'Date Stamp[:\s]*([0-9]{2}[/\-][0-9]{2}[/\-][0-9]{2,4})',
            ],
            'branch': [
                r'(?:BRANCH|Branch)[:\s]*([A-Za-z\s]{3,30})',
                r'([A-Za-z]+\s+(?:BRANCH))',
                r'Branch Name[:\s]*([A-Za-z\s]+)',
            ],
            'source_of_funds': [
                r'Source\s*of\s*Funds[:\s]*([A-Za-z\s]+)',
                r'Source of Funds[:\s]*([A-Za-z\s]+)',
            ],
            'application_of_transaction': [
                r'Application\s*of\s*Transaction[:\s]*([A-Za-z\s]+)',
                r'Application of Transaction[:\s]*([A-Za-z\s]+)',
            ],
            'phone_number': [
                r'Company\'s\s*Telephone\s*Number[:\s]*([0-9]{10,12})',
                r'Telephone[:\s]*([0-9]{10,12})',
                r'Phone[:\s]*([0-9]{10,12})',
            ]
        }
        
        # NBS specific denomination patterns for amount extraction
        self.denomination_pattern = re.compile(
            r'K(5000|2000|1000|500|200|100|50|20|10|5)\s+\|\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)',
            re.IGNORECASE
        )
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Increase contrast
        gray = cv2.equalizeHist(gray)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # Apply adaptive thresholding
        processed = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Denoise
        processed = cv2.medianBlur(processed, 3)
        
        # Optional: Dilate to make text more visible
        kernel = np.ones((2, 2), np.uint8)
        processed = cv2.dilate(processed, kernel, iterations=1)
        
        return processed
    
    def extract_text(self, image: np.ndarray, use_multiple_psm: bool = True) -> str:
        """Extract text using Tesseract OCR with multiple PSM modes"""
        all_text = []
        
        # Try different PSM (Page Segmentation Mode) settings for better results
        psm_modes = [6, 3, 4, 11, 12] if use_multiple_psm else [6]
        
        for psm in psm_modes:
            config = f'--oem 3 --psm {psm} -l eng'
            try:
                text = pytesseract.image_to_string(image, config=config)
                if text and len(text.strip()) > 50:  # Only keep if substantial text
                    all_text.append(text)
            except Exception as e:
                logger.warning(f"PSM {psm} failed: {e}")
                continue
        
        # Combine unique lines from all attempts
        combined_lines = set()
        for text in all_text:
            for line in text.split('\n'):
                if line.strip():
                    combined_lines.add(line.strip())
        
        return '\n'.join(combined_lines)
    
    def extract_fields(self, text: str) -> Dict:
        """Extract fields using regex"""
        extracted = {}
        
        for field, patterns in self.patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    value = matches[0].strip() if isinstance(matches[0], str) else str(matches[0])
                    if value and len(value) > 1:
                        extracted[field] = value
                        break
        
        return extracted
    
    def extract_amount_from_denominations(self, text: str) -> Optional[float]:
        """Extract total amount from denomination table (NBS deposit slip specific)"""
        total = 0.0
        
        # Look for denomination pattern
        matches = self.denomination_pattern.findall(text)
        for match in matches:
            denomination = int(match[0])
            # Parse the quantity (handles formats like "2 00 0 00" for 2000)
            quantity_str = ''.join(match[1:]).strip()
            try:
                quantity = int(quantity_str)
                total += denomination * quantity
            except ValueError:
                continue
        
        # Look for Total field
        total_patterns = [
            r'TOTAL[:\s]*(\d+(?:\s*\d+)*)',
            r'Total[:\s]*(\d+(?:\s*\d+)*)',
            r'TOTAL\s+MWK[:\s]*(\d+(?:,\d+)*(?:\.\d{2})?)',
        ]
        
        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                total_str = match.group(1).replace(' ', '').replace(',', '')
                try:
                    total = float(total_str)
                    break
                except:
                    continue
        
        return total if total > 0 else None
    
    def identify_bank(self, text: str) -> Optional[str]:
        """Identify bank from text with NBS specific detection"""
        text_lower = text.lower()
        
        # Special detection for NBS Bank
        nbs_indicators = ['nbs bank', 'bic f d', 'bicfd', 'cash deposit slip']
        for indicator in nbs_indicators:
            if indicator in text_lower:
                return 'NBS Bank'
        
        for bank, keywords in self.bank_patterns.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return bank
        return None
    
    def clean_amount(self, amount_str: str) -> Optional[float]:
        """Convert amount string to float"""
        try:
            # Remove spaces, commas, and handle various formats
            cleaned = amount_str.replace(',', '').replace(' ', '').replace('MWK', '').strip()
            # Handle cases like "2 00 0 00" -> "20000"
            cleaned = re.sub(r'\s+', '', cleaned)
            return float(cleaned)
        except:
            return None
    
    def calculate_confidence(self, extracted: Dict, bank_found: bool, text: str) -> float:
        """Calculate confidence score based on extracted fields"""
        score = 0.0
        total = 7  # reference, amount, account, depositor, bank, source, application
        
        if extracted.get('reference'):
            score += 1
        if extracted.get('amount'):
            score += 1
        if extracted.get('account'):
            score += 1
        if extracted.get('depositor'):
            score += 0.5
        if bank_found:
            score += 1
        if extracted.get('source_of_funds'):
            score += 0.5
        if extracted.get('application_of_transaction'):
            score += 0.5
        
        # Bonus for NBS specific patterns
        if 'nbs' in text.lower() or 'bic f d' in text.lower():
            score += 1
            total += 1
        
        return min(score / total, 1.0)
    
    def recognize(self, file) -> Dict[str, Any]:
        """Main recognition method with enhanced NBS deposit slip support"""
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
                    if img is None:
                        return {'success': False, 'error': 'Could not decode image'}
            else:
                img = file  # Already numpy array
            
            # Preprocess and extract text
            processed = self.preprocess_image(img)
            text = self.extract_text(processed)
            
            # Also try with original image for comparison
            original_text = self.extract_text(img, use_multiple_psm=True)
            combined_text = text + '\n' + original_text
            
            if not combined_text.strip():
                return {
                    'success': False,
                    'error': 'No text could be extracted from the image',
                    'extracted_data': None
                }
            
            logger.info(f"Extracted text preview: {combined_text[:500]}")
            
            # Extract data
            extracted = self.extract_fields(combined_text)
            bank = self.identify_bank(combined_text)
            
            # Special amount extraction for NBS deposit slips
            amount = extracted.get('amount')
            if amount:
                amount = self.clean_amount(amount)
            else:
                # Try to extract from denomination table
                amount = self.extract_amount_from_denominations(combined_text)
            
            # Calculate confidence
            confidence = self.calculate_confidence(extracted, bank is not None, combined_text)
            
            # Prepare result
            result_data = {
                'reference_number': extracted.get('reference'),
                'amount': amount,
                'account_number': extracted.get('account'),
                'depositor_name': extracted.get('depositor'),
                'bank_name': bank,
                'transaction_date': extracted.get('date'),
                'branch_name': extracted.get('branch'),
                'confidence_score': confidence,
                'source_of_funds': extracted.get('source_of_funds'),
                'application_of_transaction': extracted.get('application_of_transaction'),
                'phone_number': extracted.get('phone_number'),
            }
            
            result = {
                'success': True,
                'extracted_data': result_data,
                'raw_text_preview': combined_text[:1000]  # Increased preview length
            }
            
            logger.info(f"Recognition successful. Bank: {bank}, Confidence: {confidence}")
            
            return result
            
        except Exception as e:
            logger.error(f"Recognition error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'extracted_data': None
            }
    
    def is_valid_deposit_slip(self, file) -> Tuple[bool, float, Dict]:
        """
        Quick validation to check if a file is a valid deposit slip
        Returns: (is_valid, confidence, extracted_info)
        """
        result = self.recognize(file)
        
        if not result.get('success'):
            return False, 0.0, {}
        
        extracted = result.get('extracted_data', {})
        confidence = extracted.get('confidence_score', 0.0)
        
        # A valid deposit slip should have at least:
        # - A bank name OR
        # - A reference number OR amount
        is_valid = (
            confidence >= 0.4 or
            extracted.get('bank_name') is not None or
            (extracted.get('reference_number') and extracted.get('amount')) or
            (extracted.get('account_number') and extracted.get('depositor_name'))
        )
        
        return is_valid, confidence, extracted


# Singleton instance
deposit_slip_recognizer = DepositSlipRecognizer()