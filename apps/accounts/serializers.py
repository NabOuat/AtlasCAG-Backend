from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Utilisateur


class UtilisateurMeSerializer(serializers.ModelSerializer):
    class Meta:
        model        = Utilisateur
        fields       = ['id', 'username', 'first_name', 'last_name', 'email', 'profil', 'is_staff']
        read_only_fields = fields


class UtilisateurListSerializer(serializers.ModelSerializer):
    nom_complet = serializers.SerializerMethodField()

    class Meta:
        model  = Utilisateur
        fields = ['id', 'username', 'first_name', 'last_name', 'nom_complet',
                  'email', 'profil', 'is_active', 'is_staff', 'date_joined']

    @extend_schema_field(serializers.CharField())
    def get_nom_complet(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip() or obj.username


class UtilisateurCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model  = Utilisateur
        fields = ['username', 'first_name', 'last_name', 'email', 'profil', 'password', 'is_active']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user     = Utilisateur(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UtilisateurUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Utilisateur
        fields = ['first_name', 'last_name', 'email', 'profil', 'is_active']
