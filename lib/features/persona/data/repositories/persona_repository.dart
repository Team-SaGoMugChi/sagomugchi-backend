import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

import '../../../../core/error/app_exception.dart';
import '../models/persona_config.dart';

/// Chatbot-persona settings storage (`users/{uid}/meta/persona` —
/// FIRESTORE_SCHEMA.md). The Phase-5 counseling bot reads this for its
/// system prompt.
abstract interface class PersonaRepository {
  Future<PersonaConfig?> fetchPersona();

  Future<void> savePersona(PersonaConfig config);
}

class PersonaFirestoreRepository implements PersonaRepository {
  PersonaFirestoreRepository({FirebaseAuth? auth, FirebaseFirestore? firestore})
      : _auth = auth ?? FirebaseAuth.instance,
        _firestore = firestore ?? FirebaseFirestore.instance;

  final FirebaseAuth _auth;
  final FirebaseFirestore _firestore;

  DocumentReference<Map<String, dynamic>> get _doc {
    final uid = _auth.currentUser?.uid;
    if (uid == null) {
      throw const AuthException('로그인이 필요해요. 다시 로그인해주세요.');
    }
    return _firestore
        .collection('users')
        .doc(uid)
        .collection('meta')
        .doc('persona');
  }

  @override
  Future<PersonaConfig?> fetchPersona() {
    return _guard(() async {
      final snapshot = await _doc.get();
      final data = snapshot.data();
      return data != null ? PersonaConfig.fromJson(data) : null;
    });
  }

  @override
  Future<void> savePersona(PersonaConfig config) {
    return _guard(() => _doc.set(config.toJson()));
  }

  Future<T> _guard<T>(Future<T> Function() run) async {
    try {
      return await run();
    } on FirebaseException catch (e) {
      if (e.code == 'unavailable') {
        throw NetworkException('네트워크 연결이 불안정해요.', e);
      }
      throw ServerException('설정을 저장하지 못했어요. 잠시 후 다시 시도해주세요.', e);
    }
  }
}

/// In-memory persona for tests/prototyping.
class PersonaDummyRepository implements PersonaRepository {
  PersonaConfig? _config;

  @override
  Future<PersonaConfig?> fetchPersona() async => _config;

  @override
  Future<void> savePersona(PersonaConfig config) async => _config = config;
}
