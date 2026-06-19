import sys
import os
import traceback
import json

# Add app dir to path to import ai_engine
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

from ai_engine import (
    _build_summary,
    _enforce_valuation_coherence,
    _model_weighted_valuation,
    _reconcile_narrative_with_verdict,
    _ensure_company_specific_outputs,
    _fallback
)

def run_tests():
    bugs_found = []

    test_cases = [
        ("Empty dict", {}),
        ("Dict with empty key_metrics", {"key_metrics": {}}),
        ("Missing company_name in sd", {"ticker": "AAPL", "key_metrics": {}}),
        ("None in key_metrics", {"key_metrics": None}),
        ("None in advanced_models", {"key_metrics": {}, "advanced_models": None}),
        ("Malformed result dict for valuation coherence", {"key_metrics": {"current_price": 100}}),
        ("String instead of float for price", {"key_metrics": {"current_price": "100.0"}}),
    ]

    for name, sd in test_cases:
        # Test _build_summary
        try:
            _build_summary(sd)
        except Exception as e:
            bugs_found.append(("build_summary", name, traceback.format_exc()))
            
        # Test _enforce_valuation_coherence
        try:
            res = {}
            _enforce_valuation_coherence(res, sd)
        except Exception as e:
            bugs_found.append(("enforce_valuation_coherence", name, traceback.format_exc()))

        # Test _model_weighted_valuation
        try:
            res = {}
            _model_weighted_valuation(res, sd)
        except Exception as e:
            bugs_found.append(("model_weighted_valuation", name, traceback.format_exc()))
            
        # Test _fallback
        try:
            _fallback(sd)
        except Exception as e:
            bugs_found.append(("fallback", name, traceback.format_exc()))
            
        # Test _ensure_company_specific_outputs
        try:
            res = {}
            _ensure_company_specific_outputs(res, sd)
        except Exception as e:
            bugs_found.append(("ensure_company_specific_outputs", name, traceback.format_exc()))
            
        # Test _reconcile_narrative_with_verdict
        try:
            res = {}
            _reconcile_narrative_with_verdict(res, original_valuation=None, stock_data=sd)
        except Exception as e:
            bugs_found.append(("reconcile_narrative_with_verdict", name, traceback.format_exc()))

    # Try string instead of dict for nested structures in _ensure_company_specific_outputs
    try:
        sd = {"ticker": "AAPL", "key_metrics": {}}
        res = {"fundamental_analysis": "This is a string", "valuation_assessment": ["list"]}
        _ensure_company_specific_outputs(res, sd)
    except Exception as e:
        bugs_found.append(("ensure_company_specific_outputs", "Malformed result dict string types", traceback.format_exc()))

    if bugs_found:
        print(f"Found {len(bugs_found)} bugs!")
        for func, case, tb in bugs_found:
            print(f"--- BUG in {func} | Case: {case} ---")
            print(tb)
    else:
        print("No bugs found.")

if __name__ == '__main__':
    run_tests()
